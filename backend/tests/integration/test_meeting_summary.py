"""Commit 12 — Claude Sonnet meeting summary + action items.

Covers:
  - submit_summary: no-op when anthropic_api_key missing
  - submit_summary: no-op when transcript isn't AVAILABLE
  - submit_summary: empty-audio path writes empty AVAILABLE summary
  - submit_summary: happy path persists AVAILABLE row + populates
    summary_text + topics + action_items + next_steps + token counts
  - submit_summary: idempotent — second call returns existing row
  - submit_summary: FAILED rows can be re-driven
  - submit_summary: invalid-JSON Claude response → FAILED with error
    surfaced; meeting state intact
  - drive_pending_summaries: queues AVAILABLE transcripts without a
    summary; skips when no API key

The Claude SDK is monkey-patched — we test OUR pipeline, not Claude's.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import summarization
from app.meetings.models import (
    Meeting, MeetingRecording, MeetingStatus, MeetingSummary,
    RecordingStatus, RecordingTranscript, SummaryStatus, TranscriptStatus,
)
from tests.conftest import TEST_SETTINGS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def settings_with_anthropic():
    return TEST_SETTINGS.model_copy(update={
        "anthropic_api_key": "fake-key",
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


@pytest_asyncio.fixture
async def available_transcript(
    db: AsyncSession, host: User,
) -> RecordingTranscript:
    m = Meeting(
        id=uuid.uuid4(), title="Q3 strategy",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"r-{uuid.uuid4().hex[:8]}",
        created_by=host.id, slug="abc-defg-hij",
    )
    db.add(m)
    rec = MeetingRecording(
        id=uuid.uuid4(),
        meeting_id=m.id, status=RecordingStatus.AVAILABLE,
        storage_path="meetings/x/x.mp4", mime_type="video/mp4",
        started_by=host.id,
    )
    db.add(rec)
    # Flush so the recording row exists before we add the transcript
    # row that FK-references it. SQLite enforces FKs strictly inside
    # the same transaction.
    await db.flush()
    t = RecordingTranscript(
        id=uuid.uuid4(),
        meeting_id=m.id, recording_id=rec.id,
        status=TranscriptStatus.AVAILABLE,
        full_text="Speaker A: We need to send the Q3 proposal by Friday. "
                  "Speaker B: I'll write the first draft tomorrow.",
        segments_json=[],
        provider="assemblyai", provider_id="T_done",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


def _patch_claude(monkeypatch, response: dict | str, *, usage=None):
    """Patch the internal _call_claude helper so tests don't hit Anthropic."""
    async def fake_call(text, settings, template=None):
        if isinstance(response, Exception):
            raise response
        # Mimic the real return shape including observability metadata
        payload = dict(response) if isinstance(response, dict) else {}
        payload["_model"] = settings.anthropic_model
        if usage:
            payload["_input_tokens"] = usage[0]
            payload["_output_tokens"] = usage[1]
        return payload
    monkeypatch.setattr(summarization, "_call_claude", fake_call)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_submit_returns_none_when_no_api_key(
    db: AsyncSession, available_transcript: RecordingTranscript,
):
    s = TEST_SETTINGS.model_copy(update={"anthropic_api_key": ""})
    result = await summarization.submit_summary(db, available_transcript, s)
    assert result is None
    rows = await db.execute(select(MeetingSummary))
    assert rows.scalar_one_or_none() is None


async def test_submit_skips_when_transcript_not_available(
    db: AsyncSession, host: User, settings_with_anthropic,
):
    m = Meeting(
        id=uuid.uuid4(), title="x",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="xxx-yyyy-zzz",
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
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    result = await summarization.submit_summary(db, t, settings_with_anthropic)
    assert result is None


async def test_empty_transcript_writes_empty_available_summary(
    db: AsyncSession, host: User, settings_with_anthropic,
):
    """Silent-audio path: transcript is AVAILABLE but full_text is
    empty. We write an empty AVAILABLE summary so the UI doesn't
    perpetually show 'Generating…' for silent recordings."""
    m = Meeting(
        id=uuid.uuid4(), title="silent",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="aaa-bbbb-ccc",
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
        full_text="", segments_json=[],
        provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)

    result = await summarization.submit_summary(db, t, settings_with_anthropic)
    assert result is not None
    assert result.status == SummaryStatus.AVAILABLE
    assert result.action_items_json == []
    assert "No spoken audio" in (result.summary_text or "")


async def test_happy_path_persists_full_summary(
    db: AsyncSession, available_transcript: RecordingTranscript,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, {
        "summary": "Discussed Q3 proposal deadline; assigned draft to Speaker B.",
        "topics": [
            {"topic": "Q3 proposal", "decision": "Send by Friday"},
            {"topic": "Draft owner", "decision": "Speaker B writes first draft"},
        ],
        "action_items": [
            {"text": "Write Q3 proposal first draft", "assignee": "B", "due_hint": "tomorrow"},
            {"text": "Send Q3 proposal", "assignee": "A", "due_hint": "Friday"},
        ],
        "next_steps": ["Review draft on Thursday", "Send Friday morning"],
    }, usage=(8500, 1200))

    result = await summarization.submit_summary(
        db, available_transcript, settings_with_anthropic,
    )
    assert result is not None
    assert result.status == SummaryStatus.AVAILABLE
    assert "Q3 proposal" in (result.summary_text or "")
    assert len(result.topics_json) == 2
    assert len(result.action_items_json) == 2
    assert result.action_items_json[0]["assignee"] == "B"
    assert result.input_tokens == 8500
    assert result.output_tokens == 1200
    assert result.model_used == "claude-sonnet-4-6"


async def test_submit_is_idempotent(
    db: AsyncSession, available_transcript: RecordingTranscript,
    settings_with_anthropic, monkeypatch,
):
    calls = {"count": 0}
    async def fake_call(text, settings, template=None):
        calls["count"] += 1
        return {"summary": "ok", "topics": [], "action_items": [], "next_steps": []}
    monkeypatch.setattr(summarization, "_call_claude", fake_call)

    r1 = await summarization.submit_summary(
        db, available_transcript, settings_with_anthropic,
    )
    r2 = await summarization.submit_summary(
        db, available_transcript, settings_with_anthropic,
    )
    assert r1.id == r2.id
    assert calls["count"] == 1


async def test_failed_summary_can_be_resubmitted(
    db: AsyncSession, available_transcript: RecordingTranscript,
    settings_with_anthropic, monkeypatch,
):
    failed = MeetingSummary(
        meeting_id=available_transcript.meeting_id,
        recording_transcript_id=available_transcript.id,
        status=SummaryStatus.FAILED,
        error_message="Transient outage",
    )
    db.add(failed)
    await db.commit()

    _patch_claude(monkeypatch, {
        "summary": "Retry worked", "topics": [], "action_items": [], "next_steps": [],
    })

    result = await summarization.submit_summary(
        db, available_transcript, settings_with_anthropic,
    )
    assert result.id == failed.id
    assert result.status == SummaryStatus.AVAILABLE
    assert result.error_message is None
    assert result.summary_text == "Retry worked"


async def test_invalid_json_response_marks_failed(
    db: AsyncSession, available_transcript: RecordingTranscript,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, ValueError("Claude returned non-JSON: foo bar"))
    result = await summarization.submit_summary(
        db, available_transcript, settings_with_anthropic,
    )
    assert result is not None
    assert result.status == SummaryStatus.FAILED
    assert "non-JSON" in (result.error_message or "")


async def test_drive_pending_finds_transcripts_without_summary(
    db: AsyncSession, available_transcript: RecordingTranscript,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, {
        "summary": "ok", "topics": [], "action_items": [], "next_steps": [],
    })
    result = await summarization.drive_pending_summaries(
        db, settings_with_anthropic,
    )
    assert result["processed"] == 1
    assert result["failed"] == 0


async def test_drive_pending_skips_when_no_api_key(db: AsyncSession):
    s = TEST_SETTINGS.model_copy(update={"anthropic_api_key": ""})
    result = await summarization.drive_pending_summaries(db, s)
    assert result == {"processed": 0, "failed": 0}
