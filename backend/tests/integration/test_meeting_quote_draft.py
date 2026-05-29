"""Commit 15 — AI quote/invoice draft + review gate.

Covers:
  - submit_quote_draft: no-op when anthropic_api_key missing
  - submit_quote_draft: no-op when summary not AVAILABLE
  - submit_quote_draft: SKIPPED path persists with reason
  - submit_quote_draft: AVAILABLE path persists with line items + total
    + confidence + token counts
  - submit_quote_draft: idempotent (SKIPPED + AVAILABLE both treated as
    terminal — no re-call)
  - submit_quote_draft: FAILED rows can be re-driven
  - submit_quote_draft: invalid JSON → FAILED with error_message
  - drive_pending_quote_drafts: queues AVAILABLE summaries without a
    draft; counts processed / skipped / failed
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import quote_draft
from app.meetings.models import (
    Meeting, MeetingQuoteDraft, MeetingRecording, MeetingSummary,
    QuoteDraftStatus, RecordingStatus, RecordingTranscript, SummaryStatus,
    TranscriptStatus,
)
from tests.conftest import TEST_SETTINGS


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
async def available_summary(
    db: AsyncSession, host: User,
) -> MeetingSummary:
    m = Meeting(
        id=uuid.uuid4(), title="t",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"r-{uuid.uuid4().hex[:6]}",
        created_by=host.id, slug=f"s-{uuid.uuid4().hex[:6]}",
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
        full_text="We need a Q3 cash flow review. Scope is 12 hours at $250/hr.",
        segments_json=[], provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.flush()
    s = MeetingSummary(
        meeting_id=m.id, recording_transcript_id=t.id,
        status=SummaryStatus.AVAILABLE,
        summary_text="Client wants a Q3 cash flow review.",
        action_items_json=[
            {"text": "Send proposal", "assignee": "Host", "due_hint": "Friday"},
        ],
        topics_json=[], next_steps_json=[],
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


def _patch_claude(monkeypatch, response):
    async def fake_call(summary, transcript, settings):
        if isinstance(response, Exception):
            raise response
        payload = dict(response) if isinstance(response, dict) else {}
        payload["_model"] = settings.anthropic_model
        payload["_input_tokens"] = 9500
        payload["_output_tokens"] = 800
        return payload
    monkeypatch.setattr(quote_draft, "_call_claude", fake_call)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_submit_returns_none_without_api_key(
    db: AsyncSession, available_summary: MeetingSummary,
):
    s = TEST_SETTINGS.model_copy(update={"anthropic_api_key": ""})
    result = await quote_draft.submit_quote_draft(db, available_summary, s)
    assert result is None


async def test_submit_no_op_when_summary_not_available(
    db: AsyncSession, host: User, settings_with_anthropic,
):
    m = Meeting(
        id=uuid.uuid4(), title="t",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="x",
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
        status=SummaryStatus.PROCESSING,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    result = await quote_draft.submit_quote_draft(db, s, settings_with_anthropic)
    assert result is None


async def test_skipped_path_persists_with_reason(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, {"skip": True, "reason": "Internal sync, no client work discussed."})
    result = await quote_draft.submit_quote_draft(
        db, available_summary, settings_with_anthropic,
    )
    assert result.status == QuoteDraftStatus.SKIPPED
    assert "Internal sync" in (result.notes or "")
    assert result.line_items_json is None
    assert result.input_tokens == 9500


async def test_available_path_persists_full_draft(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, {
        "title": "Q3 cash flow review engagement",
        "summary": "12 hours of Q3 cash flow analysis + recommendations",
        "line_items": [
            {"description": "Q3 cash flow review", "quantity": 12, "unit_price": 250.0, "total": 3000.0},
        ],
        "estimated_total": 3000.0,
        "currency": "USD",
        "notes": "Net 15 terms discussed",
        "confidence": "high",
    })
    result = await quote_draft.submit_quote_draft(
        db, available_summary, settings_with_anthropic,
    )
    assert result.status == QuoteDraftStatus.AVAILABLE
    assert result.draft_title == "Q3 cash flow review engagement"
    assert len(result.line_items_json) == 1
    assert result.line_items_json[0]["total"] == 3000.0
    assert result.estimated_total == 3000.0
    assert result.currency == "USD"
    assert result.confidence == "high"
    assert result.input_tokens == 9500


async def test_submit_is_idempotent(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    calls = {"count": 0}
    async def fake_call(summary, transcript, settings):
        calls["count"] += 1
        return {
            "title": "x", "summary": "x",
            "line_items": [{"description": "x", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
            "estimated_total": 100.0, "currency": "USD",
            "notes": None, "confidence": "low",
        }
    monkeypatch.setattr(quote_draft, "_call_claude", fake_call)

    r1 = await quote_draft.submit_quote_draft(db, available_summary, settings_with_anthropic)
    r2 = await quote_draft.submit_quote_draft(db, available_summary, settings_with_anthropic)
    assert r1.id == r2.id
    assert calls["count"] == 1


async def test_failed_draft_can_be_resubmitted(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    failed = MeetingQuoteDraft(
        meeting_id=available_summary.meeting_id,
        summary_id=available_summary.id,
        status=QuoteDraftStatus.FAILED, error_message="Old error",
    )
    db.add(failed)
    await db.commit()

    _patch_claude(monkeypatch, {"skip": True, "reason": "no scope"})
    result = await quote_draft.submit_quote_draft(
        db, available_summary, settings_with_anthropic,
    )
    assert result.id == failed.id
    assert result.status == QuoteDraftStatus.SKIPPED
    assert result.error_message is None


async def test_invalid_json_response_marks_failed(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, ValueError("Claude returned non-JSON: blah"))
    result = await quote_draft.submit_quote_draft(
        db, available_summary, settings_with_anthropic,
    )
    assert result.status == QuoteDraftStatus.FAILED
    assert "non-JSON" in (result.error_message or "")


async def test_drive_pending_counts_processed_and_skipped(
    db: AsyncSession, available_summary: MeetingSummary,
    settings_with_anthropic, monkeypatch,
):
    _patch_claude(monkeypatch, {"skip": True, "reason": "no scope"})
    result = await quote_draft.drive_pending_quote_drafts(
        db, settings_with_anthropic,
    )
    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert result["failed"] == 0
