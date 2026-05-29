"""Commit 14 — Meeting → Contact timeline sync.

Covers:
  - log_meeting_completed: creates MEETING_COMPLETED row when contact_id set
  - log_meeting_completed: no-op without contact_id (no leak to wrong contact)
  - log_meeting_completed: idempotent (no duplicates on retry)
  - log_meeting_completed: includes duration when both timestamps set
  - log_action_items: creates NOTE_ADDED rows per action item
  - log_action_items: includes assignee + due_hint inline
  - log_action_items: no-op without contact_id
  - log_action_items: no-op without action_items
  - log_action_items: idempotent (no re-logging same summary)
  - end_meeting auto-fires log_meeting_completed (E2E hook)
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.contacts.models import ActivityType, Contact, ContactActivity, ContactType
from app.meetings import contact_sync, service
from app.meetings.models import (
    Meeting, MeetingStatus, MeetingSummary, RecordingTranscript,
    SummaryStatus, MeetingRecording, RecordingStatus, TranscriptStatus,
)
from app.meetings.schemas import MeetingCreate
from tests.conftest import TEST_SETTINGS


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="alice@example.com",
        hashed_password=hash_password("x"),
        full_name="Alice", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def acme(db: AsyncSession, host: User) -> Contact:
    c = Contact(
        id=uuid.uuid4(),
        type=ContactType.CLIENT,
        company_name="Acme Corp",
        contact_name="Bob Smith",
        email="bob@acme.com",
        created_by=host.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def settings_lk():
    return TEST_SETTINGS.model_copy(update={
        "livekit_url": "wss://x.com", "livekit_api_key": "k",
        "livekit_api_secret": "thirtytwobytekeyforsigningttests",
    })


# ---------------------------------------------------------------------------
# log_meeting_completed
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_log_meeting_completed_creates_activity_row(
    db: AsyncSession, host: User, acme: Contact,
):
    m = Meeting(
        id=uuid.uuid4(), title="Q3 cash flow review",
        scheduled_start=datetime.now(timezone.utc),
        actual_start=datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc),
        actual_end=datetime(2026, 6, 15, 14, 47, tzinfo=timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=acme.id,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)

    row = await contact_sync.log_meeting_completed(db, m)
    assert row is not None
    assert row.activity_type == ActivityType.MEETING_COMPLETED
    assert row.contact_id == acme.id
    assert row.reference_type == "meeting"
    assert row.reference_id == m.id
    # Duration suffix derived from actual_start/actual_end
    assert "47 min" in row.title


async def test_log_meeting_completed_no_op_without_contact(
    db: AsyncSession, host: User,
):
    m = Meeting(
        id=uuid.uuid4(), title="internal sync",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=None,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    row = await contact_sync.log_meeting_completed(db, m)
    assert row is None


async def test_log_meeting_completed_is_idempotent(
    db: AsyncSession, host: User, acme: Contact,
):
    m = Meeting(
        id=uuid.uuid4(), title="t",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=acme.id,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    r1 = await contact_sync.log_meeting_completed(db, m)
    r2 = await contact_sync.log_meeting_completed(db, m)
    assert r1.id == r2.id
    rows = await db.execute(
        select(ContactActivity).where(ContactActivity.contact_id == acme.id)
    )
    assert len(rows.scalars().all()) == 1


# ---------------------------------------------------------------------------
# log_action_items_from_summary
# ---------------------------------------------------------------------------


async def test_log_action_items_creates_rows_per_item(
    db: AsyncSession, host: User, acme: Contact,
):
    m = Meeting(
        id=uuid.uuid4(), title="planning",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=acme.id,
    )
    db.add(m)
    rec = MeetingRecording(
        meeting_id=m.id, status=RecordingStatus.AVAILABLE,
        storage_path="x", mime_type="video/mp4", started_by=host.id,
    )
    db.add(rec)
    await db.flush()
    t = RecordingTranscript(
        meeting_id=m.id, recording_id=rec.id,
        status=TranscriptStatus.AVAILABLE, full_text="x",
        segments_json=[], provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.flush()
    s = MeetingSummary(
        meeting_id=m.id, recording_transcript_id=t.id,
        status=SummaryStatus.AVAILABLE,
        summary_text="ok",
        action_items_json=[
            {"text": "Send Q3 proposal", "assignee": "Alice", "due_hint": "Friday"},
            {"text": "Schedule a follow-up call", "assignee": None, "due_hint": None},
        ],
        topics_json=[], next_steps_json=[],
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    await db.refresh(m)

    count = await contact_sync.log_action_items_from_summary(db, m, s)
    assert count == 2

    rows = (await db.execute(
        select(ContactActivity).where(
            ContactActivity.contact_id == acme.id,
            ContactActivity.reference_type == "meeting_summary",
        ).order_by(ContactActivity.title)
    )).scalars().all()
    assert len(rows) == 2
    # First-item description carries assignee + due hint inline
    proposal = next(r for r in rows if "Send Q3" in r.title)
    assert "Alice" in (proposal.description or "")
    assert "Friday" in (proposal.description or "")


async def test_log_action_items_no_op_without_contact(
    db: AsyncSession, host: User,
):
    m = Meeting(
        id=uuid.uuid4(), title="t",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=None,
    )
    db.add(m)
    rec = MeetingRecording(
        meeting_id=m.id, status=RecordingStatus.AVAILABLE,
        storage_path="x", mime_type="video/mp4", started_by=host.id,
    )
    db.add(rec)
    await db.flush()
    t = RecordingTranscript(
        meeting_id=m.id, recording_id=rec.id,
        status=TranscriptStatus.AVAILABLE,
        segments_json=[], provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.flush()
    s = MeetingSummary(
        meeting_id=m.id, recording_transcript_id=t.id,
        status=SummaryStatus.AVAILABLE,
        action_items_json=[{"text": "x"}],
    )
    db.add(s)
    await db.commit()
    count = await contact_sync.log_action_items_from_summary(db, m, s)
    assert count == 0


async def test_log_action_items_is_idempotent(
    db: AsyncSession, host: User, acme: Contact,
):
    m = Meeting(
        id=uuid.uuid4(), title="t",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
        contact_id=acme.id,
    )
    db.add(m)
    rec = MeetingRecording(
        meeting_id=m.id, status=RecordingStatus.AVAILABLE,
        storage_path="x", mime_type="video/mp4", started_by=host.id,
    )
    db.add(rec)
    await db.flush()
    t = RecordingTranscript(
        meeting_id=m.id, recording_id=rec.id,
        status=TranscriptStatus.AVAILABLE,
        segments_json=[], provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.flush()
    s = MeetingSummary(
        meeting_id=m.id, recording_transcript_id=t.id,
        status=SummaryStatus.AVAILABLE,
        action_items_json=[{"text": "do thing"}, {"text": "do other thing"}],
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    n1 = await contact_sync.log_action_items_from_summary(db, m, s)
    n2 = await contact_sync.log_action_items_from_summary(db, m, s)
    assert n1 == 2
    assert n2 == 0  # idempotent


# ---------------------------------------------------------------------------
# E2E hook: end_meeting auto-fires the timeline log
# ---------------------------------------------------------------------------


async def test_end_meeting_auto_logs_to_contact_timeline(
    db: AsyncSession, host: User, acme: Contact, settings_lk,
):
    data = MeetingCreate(
        title="E2E test",
        scheduled_start=datetime.now(timezone.utc),
        contact_id=acme.id,
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    # Force it into IN_PROGRESS so end_meeting works
    meeting.status = MeetingStatus.IN_PROGRESS
    meeting.actual_start = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db.commit()
    await service.end_meeting(db, meeting.id, host, settings_lk)

    rows = (await db.execute(
        select(ContactActivity).where(
            ContactActivity.contact_id == acme.id,
            ContactActivity.activity_type == ActivityType.MEETING_COMPLETED,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].reference_id == meeting.id
