"""Commit 17 — cross-meeting context (prior meeting + recent action items).

Covers:
  - empty when meeting has no contact_id
  - returns last completed meeting with the same contact (title + date)
  - includes summary_text from the prior meeting's latest AVAILABLE summary
  - excludes scheduled (future) prior meetings from "last meeting"
  - excludes the current meeting itself
  - recent action items pulled from ContactActivity (Commit 14)
  - recent topics pulled from the prior meeting's summary
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.contacts.models import ActivityType, Contact, ContactActivity, ContactType
from app.meetings.cross_context import get_prior_context_for_meeting
from app.meetings.models import (
    Meeting, MeetingRecording, MeetingStatus, MeetingSummary,
    RecordingStatus, RecordingTranscript, SummaryStatus, TranscriptStatus,
)


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="host@example.com",
        hashed_password=hash_password("x"),
        full_name="Host", role=Role.ACCOUNTANT,
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
        company_name="Acme",
        contact_name="Client",
        email="c@acme.com",
        created_by=host.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _make_meeting(
    db: AsyncSession, host: User, contact_id: uuid.UUID | None,
    *,
    title: str,
    status: MeetingStatus = MeetingStatus.COMPLETED,
    days_ago: int = 0,
) -> Meeting:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    m = Meeting(
        id=uuid.uuid4(), title=title,
        scheduled_start=when,
        actual_start=when if status == MeetingStatus.COMPLETED else None,
        actual_end=when + timedelta(minutes=30) if status == MeetingStatus.COMPLETED else None,
        livekit_room_name=f"r-{uuid.uuid4().hex[:8]}",
        created_by=host.id, slug=f"s-{uuid.uuid4().hex[:8]}",
        contact_id=contact_id, status=status,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _attach_summary(
    db: AsyncSession, host: User, m: Meeting,
    *, summary_text: str, topics: list[dict],
) -> MeetingSummary:
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
        summary_text=summary_text,
        topics_json=topics,
        action_items_json=[], next_steps_json=[],
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_empty_when_meeting_has_no_contact(db: AsyncSession, host: User):
    m = await _make_meeting(db, host, contact_id=None, title="ad-hoc")
    payload = await get_prior_context_for_meeting(db, m)
    assert payload == {}


async def test_returns_last_completed_meeting_with_summary(
    db: AsyncSession, host: User, acme: Contact,
):
    prior = await _make_meeting(
        db, host, contact_id=acme.id, title="Q2 review", days_ago=14,
    )
    await _attach_summary(
        db, host, prior,
        summary_text="Q2 cash flow was stable; client extended retainer.",
        topics=[
            {"topic": "Cash flow", "decision": "stable"},
            {"topic": "Retainer", "decision": "extended"},
        ],
    )
    current = await _make_meeting(
        db, host, contact_id=acme.id, title="Q3 review",
        status=MeetingStatus.SCHEDULED, days_ago=0,
    )
    payload = await get_prior_context_for_meeting(db, current)
    assert payload["contact_id"] == str(acme.id)
    assert payload["last_meeting"]["title"] == "Q2 review"
    assert "Q2 cash flow" in payload["last_meeting"]["summary_text"]
    assert len(payload["recent_topics"]) == 2


async def test_excludes_current_meeting_itself(
    db: AsyncSession, host: User, acme: Contact,
):
    """Even if the current meeting itself is COMPLETED, it must not
    show up as the 'last meeting' (no self-reference)."""
    m = await _make_meeting(
        db, host, contact_id=acme.id, title="Only meeting",
        status=MeetingStatus.COMPLETED, days_ago=0,
    )
    payload = await get_prior_context_for_meeting(db, m)
    assert payload["last_meeting"] is None


async def test_excludes_scheduled_future_meetings_from_last_meeting(
    db: AsyncSession, host: User, acme: Contact,
):
    """A SCHEDULED future meeting isn't 'prior context'. Only meetings
    that already happened (IN_PROGRESS or COMPLETED) count."""
    # Future scheduled meeting (would otherwise sort first by date)
    await _make_meeting(
        db, host, contact_id=acme.id, title="Future kickoff",
        status=MeetingStatus.SCHEDULED, days_ago=-7,
    )
    # Past completed meeting
    prior = await _make_meeting(
        db, host, contact_id=acme.id, title="Last call",
        status=MeetingStatus.COMPLETED, days_ago=30,
    )
    current = await _make_meeting(
        db, host, contact_id=acme.id, title="Now",
        status=MeetingStatus.SCHEDULED, days_ago=0,
    )
    payload = await get_prior_context_for_meeting(db, current)
    assert payload["last_meeting"]["title"] == "Last call"


async def test_pulls_recent_action_items_from_contact_activity(
    db: AsyncSession, host: User, acme: Contact,
):
    m_prior = await _make_meeting(
        db, host, contact_id=acme.id, title="prior", days_ago=10,
    )
    # Action items recorded in Commit 14 pattern
    a1 = ContactActivity(
        contact_id=acme.id, activity_type=ActivityType.NOTE_ADDED,
        title="Action: Send Q3 proposal",
        description="Send Q3 proposal — Alice · by Friday",
        reference_type="meeting_summary", reference_id=uuid.uuid4(),
        created_by=host.id,
    )
    a2 = ContactActivity(
        contact_id=acme.id, activity_type=ActivityType.NOTE_ADDED,
        title="Action: Follow up on draft",
        description="Follow up on draft — Bob",
        reference_type="meeting_summary", reference_id=uuid.uuid4(),
        created_by=host.id,
    )
    db.add_all([a1, a2])
    await db.commit()

    current = await _make_meeting(
        db, host, contact_id=acme.id, title="Now",
        status=MeetingStatus.SCHEDULED, days_ago=0,
    )
    payload = await get_prior_context_for_meeting(db, current)
    titles = {ai["title"] for ai in payload["recent_action_items"]}
    assert "Action: Send Q3 proposal" in titles
    assert "Action: Follow up on draft" in titles
