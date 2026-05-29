"""Commit 16 — Meeting templates (discovery / client review / internal sync).

Covers:
  - DISCOVERY_CALL template auto-enables record_meeting at create time
  - INTERNAL_SYNC template keeps record_meeting=False
  - explicit record_meeting=True overrides template default
  - _build_messages folds the per-template guidance into the prompt
  - INTERNAL_SYNC short-circuits quote draft to SKIPPED (no Claude call,
    no cost)
  - GENERIC template behaves like pre-Commit-16 (no recording, no
    guidance, quote draft attempted as normal)
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import service, summarization, quote_draft
from app.meetings.models import (
    Meeting, MeetingQuoteDraft, MeetingRecording, MeetingSummary,
    MeetingTemplate, QuoteDraftStatus, RecordingStatus,
    RecordingTranscript, SummaryStatus, TranscriptStatus,
)
from app.meetings.schemas import MeetingCreate
from tests.conftest import TEST_SETTINGS


@pytest_asyncio.fixture
async def settings_lk():
    return TEST_SETTINGS.model_copy(update={
        "livekit_url": "wss://x.com", "livekit_api_key": "k",
        "livekit_api_secret": "thirtytwobytekeyforsigningttests",
        "anthropic_api_key": "fake",
        "anthropic_model": "claude-sonnet-4-6",
    })


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


# ---------------------------------------------------------------------------
# create_meeting + template-driven defaults
# ---------------------------------------------------------------------------


async def test_discovery_call_auto_enables_recording(
    db: AsyncSession, host: User, settings_lk,
):
    data = MeetingCreate(
        title="Acme discovery",
        scheduled_start=datetime.now(timezone.utc),
        template=MeetingTemplate.DISCOVERY_CALL,
        create_calendar_event=False,
        # record_meeting NOT explicitly set → template default applies
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    assert meeting.template == MeetingTemplate.DISCOVERY_CALL
    assert meeting.record_meeting is True


async def test_internal_sync_keeps_recording_off(
    db: AsyncSession, host: User, settings_lk,
):
    data = MeetingCreate(
        title="Weekly team sync",
        scheduled_start=datetime.now(timezone.utc),
        template=MeetingTemplate.INTERNAL_SYNC,
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    assert meeting.template == MeetingTemplate.INTERNAL_SYNC
    assert meeting.record_meeting is False


async def test_explicit_record_overrides_template_default(
    db: AsyncSession, host: User, settings_lk,
):
    """Caller's explicit record_meeting=True must NOT be downgraded
    by an INTERNAL_SYNC template default."""
    data = MeetingCreate(
        title="Team retro recording",
        scheduled_start=datetime.now(timezone.utc),
        template=MeetingTemplate.INTERNAL_SYNC,
        record_meeting=True,
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    assert meeting.record_meeting is True


# ---------------------------------------------------------------------------
# Summarization prompt — template guidance folded in
# ---------------------------------------------------------------------------


def test_summary_prompt_includes_discovery_guidance():
    msgs = summarization._build_messages(
        "Speaker A: we want a quote", MeetingTemplate.DISCOVERY_CALL,
    )
    content = msgs[0]["content"]
    assert "DISCOVERY CALL" in content
    assert "scope items" in content.lower()


def test_summary_prompt_includes_internal_sync_guidance():
    msgs = summarization._build_messages(
        "x", MeetingTemplate.INTERNAL_SYNC,
    )
    content = msgs[0]["content"]
    assert "INTERNAL TEAM SYNC" in content
    assert "client-facing" in content.lower()


def test_summary_prompt_no_guidance_for_generic():
    msgs = summarization._build_messages("x", MeetingTemplate.GENERIC)
    content = msgs[0]["content"]
    # No template-specific phrases
    assert "DISCOVERY CALL" not in content
    assert "INTERNAL TEAM SYNC" not in content
    assert "CLIENT REVIEW" not in content


# ---------------------------------------------------------------------------
# Quote draft — INTERNAL_SYNC short-circuits to SKIPPED
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def summary_for_template(db: AsyncSession, host: User, settings_lk):
    """Helper that builds a Meeting + Recording + Transcript + Summary
    chain that's ready for quote_draft.submit_quote_draft to consume,
    with the template provided at call time."""
    async def _make(template: MeetingTemplate) -> MeetingSummary:
        m = Meeting(
            id=uuid.uuid4(), title="t",
            scheduled_start=datetime.now(timezone.utc),
            livekit_room_name=f"r-{uuid.uuid4().hex[:6]}",
            created_by=host.id, slug=f"s-{uuid.uuid4().hex[:6]}",
            template=template,
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
            full_text="We need a Q3 cash flow review for $3000.",
            segments_json=[], provider="assemblyai", provider_id="X",
        )
        db.add(t)
        await db.flush()
        s = MeetingSummary(
            meeting_id=m.id, recording_transcript_id=t.id,
            status=SummaryStatus.AVAILABLE,
            summary_text="discussed scope",
            action_items_json=[], topics_json=[], next_steps_json=[],
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return s
    return _make


async def test_internal_sync_short_circuits_quote_draft_to_skipped(
    db: AsyncSession, summary_for_template, settings_lk, monkeypatch,
):
    """INTERNAL_SYNC should NEVER make the Claude call — saves cost
    and avoids surfacing irrelevant quote drafts on team meetings."""
    calls = {"count": 0}
    async def fake_call(summary, transcript, settings):
        calls["count"] += 1
        return {}
    monkeypatch.setattr(quote_draft, "_call_claude", fake_call)

    s = await summary_for_template(MeetingTemplate.INTERNAL_SYNC)
    result = await quote_draft.submit_quote_draft(db, s, settings_lk)
    assert result is not None
    assert result.status == QuoteDraftStatus.SKIPPED
    assert "Internal sync" in (result.notes or "")
    assert calls["count"] == 0  # no Claude call → no cost


async def test_discovery_call_template_still_attempts_quote_draft(
    db: AsyncSession, summary_for_template, settings_lk, monkeypatch,
):
    """DISCOVERY_CALL is the prime target for quote drafts — must
    still call Claude."""
    calls = {"count": 0}
    async def fake_call(summary, transcript, settings):
        calls["count"] += 1
        return {
            "title": "Q3 review", "summary": "x",
            "line_items": [{"description": "x", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
            "estimated_total": 100.0, "currency": "USD",
            "notes": None, "confidence": "high",
        }
    monkeypatch.setattr(quote_draft, "_call_claude", fake_call)

    s = await summary_for_template(MeetingTemplate.DISCOVERY_CALL)
    result = await quote_draft.submit_quote_draft(db, s, settings_lk)
    assert result is not None
    assert result.status == QuoteDraftStatus.AVAILABLE
    assert calls["count"] == 1
