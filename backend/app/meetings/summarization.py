"""Claude-powered meeting summarization (Commit 12).

Flow:
  1. RecordingTranscript becomes AVAILABLE → submit_summary fires.
  2. We build a structured prompt asking Claude for: 2-3 sentence
     summary, topics+decisions, action items, next steps.
  3. JSON-mode response. We persist into MeetingSummary as AVAILABLE.
  4. Failures land in FAILED with error_message for operator retry.

Cost model:
  ~10K input + 1.5K output tokens per 45-min meeting transcript
  ~$0.07-0.10 per meeting on claude-sonnet-4-x
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.meetings.models import (
    MeetingSummary, RecordingTranscript, SummaryStatus, TranscriptStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SUMMARIZATION_PROMPT = """You are an accountant's AI assistant. Read the meeting transcript below and produce a structured summary suitable for the host's records and the client's follow-up.

Output STRICT JSON with this schema (no preamble, no markdown fences):

{
  "summary": "2-3 sentence neutral summary of what the meeting covered",
  "topics": [
    {"topic": "short topic name", "decision": "decision made or null"}
  ],
  "action_items": [
    {"text": "what needs to happen", "assignee": "speaker letter or name or null", "due_hint": "natural-language due date or null"}
  ],
  "next_steps": ["single-sentence next step", ...]
}

Rules:
- summary: factual, no opinions, mention the speakers' roles when clear.
- topics: 3-7 entries, ordered by importance.
- action_items: only items that imply someone WILL DO something. Skip vague aspirations. Include the assignee when the transcript identifies them.
- next_steps: 1-4 entries, future-looking.
- If the transcript is too short or off-topic to summarize, return empty arrays + a summary like "No meaningful content".

Transcript:
---
{TRANSCRIPT_TEXT}
---"""


def _build_messages(transcript_text: str) -> list[dict]:
    """Stitch the transcript into the prompt. We pass the full text;
    Claude's context window is plenty for a 45-min meeting (~10K
    tokens). Longer meetings will get truncated to the last 80K chars,
    which protects against pathological cases."""
    if len(transcript_text) > 80_000:
        transcript_text = (
            "[... transcript truncated to last 80K chars ...]\n"
            + transcript_text[-80_000:]
        )
    return [{
        "role": "user",
        "content": SUMMARIZATION_PROMPT.replace("{TRANSCRIPT_TEXT}", transcript_text),
    }]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def submit_summary(
    db: AsyncSession,
    transcript: RecordingTranscript,
    settings: Settings,
) -> MeetingSummary | None:
    """Generate + persist a meeting summary for an AVAILABLE transcript.

    Idempotent — returns the existing row when a summary already exists
    in any non-FAILED state. FAILED rows can be re-driven (operator
    retry path) by calling again.

    Returns None when Anthropic isn't configured (dev box) or when the
    transcript isn't AVAILABLE yet (caller shouldn't have called us).
    """
    if not settings.anthropic_api_key:
        logger.info(
            "meeting.summary_skipped transcript_id=%s reason=no_api_key",
            transcript.id,
        )
        return None
    if transcript.status != TranscriptStatus.AVAILABLE:
        logger.info(
            "meeting.summary_skipped transcript_id=%s reason=not_available",
            transcript.id,
        )
        return None
    if not transcript.full_text:
        # Empty audio — write an empty AVAILABLE summary so the UI
        # doesn't perpetually show "Generating…".
        existing = await db.execute(
            select(MeetingSummary).where(
                MeetingSummary.recording_transcript_id == transcript.id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = MeetingSummary(
                meeting_id=transcript.meeting_id,
                recording_transcript_id=transcript.id,
                status=SummaryStatus.AVAILABLE,
                summary_text="No spoken audio in this recording.",
                topics_json=[], action_items_json=[], next_steps_json=[],
            )
            db.add(row)
        else:
            row.status = SummaryStatus.AVAILABLE
            row.summary_text = "No spoken audio in this recording."
        await db.commit()
        await db.refresh(row)
        return row

    # Idempotency
    existing = await db.execute(
        select(MeetingSummary).where(
            MeetingSummary.recording_transcript_id == transcript.id,
        )
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row is not None and existing_row.status != SummaryStatus.FAILED:
        return existing_row

    # Build or refresh the row in PROCESSING state before the LLM call
    # so a process crash mid-call is recoverable (the scheduler can
    # re-drive it on the next tick).
    if existing_row is None:
        row = MeetingSummary(
            meeting_id=transcript.meeting_id,
            recording_transcript_id=transcript.id,
            status=SummaryStatus.PROCESSING,
        )
        db.add(row)
    else:
        row = existing_row
        row.status = SummaryStatus.PROCESSING
        row.error_message = None
    await db.commit()
    await db.refresh(row)

    try:
        result = await _call_claude(transcript.full_text, settings)
    except Exception as exc:
        row.status = SummaryStatus.FAILED
        row.error_message = str(exc)[:500]
        await db.commit()
        logger.warning(
            "meeting.summary_failed transcript_id=%s err=%s",
            transcript.id, str(exc)[:300],
        )
        return row

    row.status = SummaryStatus.AVAILABLE
    row.summary_text = result.get("summary") or ""
    row.topics_json = result.get("topics") or []
    row.action_items_json = result.get("action_items") or []
    row.next_steps_json = result.get("next_steps") or []
    row.model_used = result.get("_model")
    row.input_tokens = result.get("_input_tokens")
    row.output_tokens = result.get("_output_tokens")
    await db.commit()
    await db.refresh(row)
    logger.info(
        "meeting.summary_completed transcript_id=%s topics=%d actions=%d "
        "input_tokens=%s output_tokens=%s",
        transcript.id,
        len(row.topics_json or []),
        len(row.action_items_json or []),
        row.input_tokens, row.output_tokens,
    )

    # Commit 14 — log action items on the linked contact's timeline.
    # Best-effort: failures don't roll back the summary state change.
    try:
        # Reload the meeting eagerly (transcript only carries
        # meeting_id; we need contact_id off the meeting).
        from app.meetings.models import Meeting as _Meeting
        meeting = (await db.execute(
            select(_Meeting).where(_Meeting.id == row.meeting_id)
        )).scalar_one_or_none()
        if meeting is not None:
            from app.meetings.contact_sync import log_action_items_from_summary
            await log_action_items_from_summary(db, meeting, row)
    except Exception as exc:
        logger.warning(
            "meeting.action_items_log_failed summary_id=%s err=%s",
            row.id, str(exc)[:200],
        )

    # Commit 15 — quote/invoice draft (best-effort; never auto-sent).
    # Claude analyzes the transcript + summary and either drafts a
    # proposal or SKIPs when there's no scope/pricing content.
    try:
        from app.meetings.quote_draft import submit_quote_draft
        await submit_quote_draft(db, row, settings)
    except Exception as exc:
        logger.warning(
            "meeting.quote_draft_kickoff_failed summary_id=%s err=%s",
            row.id, str(exc)[:200],
        )

    return row


async def _call_claude(transcript_text: str, settings: Settings) -> dict[str, Any]:
    """Single Claude call returning parsed JSON + token usage. Raises
    on any error (caller maps to FAILED status)."""
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = _build_messages(transcript_text)
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=messages,
    )
    raw = (resp.content[0].text if resp.content else "").strip()
    # Strip code fences if Claude wraps the JSON
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Drop the first/last fence lines
        raw = "\n".join(l for l in lines if not l.startswith("```")).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Surface the offending head of the response in the error so
        # an operator can spot prompt-drift quickly.
        snippet = raw[:300].replace("\n", " ")
        raise ValueError(f"Claude returned non-JSON: {snippet} ({exc})")
    # Add observability metadata
    parsed["_model"] = settings.anthropic_model
    if hasattr(resp, "usage") and resp.usage is not None:
        parsed["_input_tokens"] = getattr(resp.usage, "input_tokens", None)
        parsed["_output_tokens"] = getattr(resp.usage, "output_tokens", None)
    return parsed


async def drive_pending_summaries(
    db: AsyncSession, settings: Settings, *, batch_limit: int = 5,
) -> dict:
    """Scheduler entry — find AVAILABLE transcripts without a summary
    and queue them. Runs every 5 min. The work itself happens inside
    submit_summary; this just queues the calls.

    Returns {processed, failed} for observability.
    """
    if not settings.anthropic_api_key:
        return {"processed": 0, "failed": 0}
    # Transcripts that are AVAILABLE but don't have a MeetingSummary row,
    # OR have a FAILED summary that's eligible for re-drive.
    rows = await db.execute(
        select(RecordingTranscript)
        .where(RecordingTranscript.status == TranscriptStatus.AVAILABLE)
        .limit(batch_limit * 4)  # over-fetch then filter
    )
    pending: list[RecordingTranscript] = []
    for t in rows.scalars().all():
        existing = await db.execute(
            select(MeetingSummary).where(
                MeetingSummary.recording_transcript_id == t.id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None or row.status == SummaryStatus.FAILED:
            pending.append(t)
        if len(pending) >= batch_limit:
            break

    processed = 0
    failed = 0
    for t in pending:
        try:
            result = await submit_summary(db, t, settings)
            if result is not None and result.status == SummaryStatus.AVAILABLE:
                processed += 1
            elif result is not None and result.status == SummaryStatus.FAILED:
                failed += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "meeting.summary_drive_failed transcript_id=%s err=%s",
                t.id, str(exc)[:200],
            )
    return {"processed": processed, "failed": failed}
