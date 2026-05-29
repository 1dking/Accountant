"""AI-drafted proposal/quote from a meeting transcript (Commit 15).

Highest-liability surface in the meeting pipeline — Claude reads the
transcript + summary and, if scope or pricing was discussed, drafts a
structured proposal. The draft is NEVER auto-sent. The host must
explicitly review and promote it via POST /meetings/{id}/quote-draft/review.

Run cost: extra ~$0.10/meeting on Claude only when this runs. We
short-circuit to SKIPPED when the transcript clearly has no scope or
pricing content (~70% of meetings).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.meetings.models import (
    Meeting, MeetingQuoteDraft, MeetingSummary, MeetingTemplate,
    QuoteDraftStatus, RecordingTranscript, SummaryStatus, TranscriptStatus,
)

logger = logging.getLogger(__name__)


QUOTE_PROMPT = """You are an accountant's AI assistant. Read the meeting summary + transcript and decide whether a proposal/quote should be drafted.

ONLY draft a quote when BOTH conditions are met:
  1. The transcript discusses concrete SCOPE (deliverables, services, tasks the accountant will do for the client), AND
  2. The transcript references PRICING (specific amounts, rates, ranges, or an explicit ask for a quote).

If those conditions aren't met, return {"skip": true, "reason": "<one sentence why>"}.

Otherwise, return STRICT JSON with this schema (no markdown):

{
  "title": "Proposal title — short, client-facing",
  "summary": "1-2 sentence client-facing overview",
  "line_items": [
    {"description": "what they're paying for", "quantity": 1, "unit_price": 1000.00, "total": 1000.00}
  ],
  "estimated_total": 1000.00,
  "currency": "USD",
  "notes": "Any caveats / out-of-scope / payment terms heard in the meeting, or null",
  "confidence": "high|medium|low"
}

Rules:
- confidence='high' only when exact amounts were spoken aloud.
- confidence='medium' when ranges were discussed (\"around 5k\").
- confidence='low' when scope is clear but pricing was implied/inferred.
- estimated_total MUST equal sum(line_items.total). Verify before responding.
- NEVER invent line items not grounded in the transcript.

Meeting summary (Claude-generated):
---
{SUMMARY_TEXT}
---

Action items extracted:
{ACTION_ITEMS}

Transcript:
---
{TRANSCRIPT_TEXT}
---"""


def _build_messages(summary: MeetingSummary, transcript: RecordingTranscript) -> list[dict]:
    transcript_text = transcript.full_text or ""
    if len(transcript_text) > 80_000:
        transcript_text = (
            "[... transcript truncated to last 80K chars ...]\n"
            + transcript_text[-80_000:]
        )
    action_items_text = json.dumps(summary.action_items_json or [], indent=2)
    prompt = (
        QUOTE_PROMPT
        .replace("{SUMMARY_TEXT}", summary.summary_text or "(empty)")
        .replace("{ACTION_ITEMS}", action_items_text)
        .replace("{TRANSCRIPT_TEXT}", transcript_text)
    )
    return [{"role": "user", "content": prompt}]


async def _call_claude(
    summary: MeetingSummary, transcript: RecordingTranscript, settings: Settings,
) -> dict[str, Any]:
    """Single Claude call returning parsed JSON + token usage."""
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = _build_messages(summary, transcript)
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        messages=messages,
    )
    raw = (resp.content[0].text if resp.content else "").strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.startswith("```")).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        snippet = raw[:300].replace("\n", " ")
        raise ValueError(f"Claude returned non-JSON: {snippet} ({exc})")
    parsed["_model"] = settings.anthropic_model
    if hasattr(resp, "usage") and resp.usage is not None:
        parsed["_input_tokens"] = getattr(resp.usage, "input_tokens", None)
        parsed["_output_tokens"] = getattr(resp.usage, "output_tokens", None)
    return parsed


async def submit_quote_draft(
    db: AsyncSession,
    summary: MeetingSummary,
    settings: Settings,
) -> MeetingQuoteDraft | None:
    """Generate + persist a quote draft for an AVAILABLE summary.

    Idempotent — returns existing row in any non-FAILED terminal state.
    FAILED rows can be re-driven. Returns None when Anthropic isn't
    configured or when the summary isn't AVAILABLE.
    """
    if not settings.anthropic_api_key:
        return None
    if summary.status != SummaryStatus.AVAILABLE:
        return None

    # Need the transcript text to draft properly
    transcript = (await db.execute(
        select(RecordingTranscript).where(
            RecordingTranscript.id == summary.recording_transcript_id,
        )
    )).scalar_one_or_none()
    if transcript is None or transcript.status != TranscriptStatus.AVAILABLE:
        return None

    # Commit 16 — INTERNAL_SYNC template never produces a quote draft.
    # Save the Claude call cost; persist a SKIPPED row so the
    # scheduler doesn't re-attempt.
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == summary.meeting_id)
    )).scalar_one_or_none()
    template = meeting.template if meeting else MeetingTemplate.GENERIC
    if template == MeetingTemplate.INTERNAL_SYNC:
        existing = await db.execute(
            select(MeetingQuoteDraft).where(MeetingQuoteDraft.summary_id == summary.id)
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row is not None and existing_row.status not in (
            QuoteDraftStatus.FAILED, QuoteDraftStatus.PENDING,
        ):
            return existing_row
        if existing_row is None:
            row = MeetingQuoteDraft(
                meeting_id=summary.meeting_id,
                summary_id=summary.id,
                status=QuoteDraftStatus.SKIPPED,
                notes="Internal sync — no quote draft generated.",
            )
            db.add(row)
        else:
            row = existing_row
            row.status = QuoteDraftStatus.SKIPPED
            row.notes = "Internal sync — no quote draft generated."
            row.error_message = None
        await db.commit()
        await db.refresh(row)
        return row

    # Idempotency
    existing = await db.execute(
        select(MeetingQuoteDraft).where(MeetingQuoteDraft.summary_id == summary.id)
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row is not None and existing_row.status not in (
        QuoteDraftStatus.FAILED, QuoteDraftStatus.PENDING,
    ):
        return existing_row

    # Build/refresh PROCESSING row before the call (recovery on crash)
    if existing_row is None:
        row = MeetingQuoteDraft(
            meeting_id=summary.meeting_id,
            summary_id=summary.id,
            status=QuoteDraftStatus.PROCESSING,
        )
        db.add(row)
    else:
        row = existing_row
        row.status = QuoteDraftStatus.PROCESSING
        row.error_message = None
    await db.commit()
    await db.refresh(row)

    try:
        result = await _call_claude(summary, transcript, settings)
    except Exception as exc:
        row.status = QuoteDraftStatus.FAILED
        row.error_message = str(exc)[:500]
        await db.commit()
        logger.warning(
            "meeting.quote_draft_failed summary_id=%s err=%s",
            summary.id, str(exc)[:300],
        )
        return row

    # Skip path — Claude decided there's nothing to quote
    if result.get("skip") is True:
        row.status = QuoteDraftStatus.SKIPPED
        row.notes = (result.get("reason") or "")[:1000]
        row.model_used = result.get("_model")
        row.input_tokens = result.get("_input_tokens")
        row.output_tokens = result.get("_output_tokens")
        await db.commit()
        logger.info(
            "meeting.quote_draft_skipped summary_id=%s reason=%s",
            summary.id, (row.notes or "")[:120],
        )
        return row

    row.status = QuoteDraftStatus.AVAILABLE
    row.draft_title = (result.get("title") or "")[:255]
    row.draft_summary = result.get("summary") or ""
    row.line_items_json = result.get("line_items") or []
    row.estimated_total = result.get("estimated_total")
    row.currency = result.get("currency") or "USD"
    row.notes = result.get("notes")
    row.confidence = result.get("confidence") or "low"
    row.model_used = result.get("_model")
    row.input_tokens = result.get("_input_tokens")
    row.output_tokens = result.get("_output_tokens")
    await db.commit()
    await db.refresh(row)
    logger.info(
        "meeting.quote_draft_available summary_id=%s line_items=%d total=%s confidence=%s",
        summary.id,
        len(row.line_items_json or []),
        row.estimated_total, row.confidence,
    )
    return row


async def drive_pending_quote_drafts(
    db: AsyncSession, settings: Settings, *, batch_limit: int = 5,
) -> dict:
    """Scheduler entry — find AVAILABLE summaries without a quote draft
    and queue them. Returns {processed, skipped, failed}."""
    if not settings.anthropic_api_key:
        return {"processed": 0, "skipped": 0, "failed": 0}
    rows = await db.execute(
        select(MeetingSummary)
        .where(MeetingSummary.status == SummaryStatus.AVAILABLE)
        .limit(batch_limit * 4)
    )
    pending: list[MeetingSummary] = []
    for s in rows.scalars().all():
        existing = await db.execute(
            select(MeetingQuoteDraft).where(
                MeetingQuoteDraft.summary_id == s.id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None or row.status == QuoteDraftStatus.FAILED:
            pending.append(s)
        if len(pending) >= batch_limit:
            break

    processed = 0
    skipped = 0
    failed = 0
    for s in pending:
        try:
            r = await submit_quote_draft(db, s, settings)
            if r is None:
                continue
            if r.status == QuoteDraftStatus.AVAILABLE:
                processed += 1
            elif r.status == QuoteDraftStatus.SKIPPED:
                skipped += 1
            elif r.status == QuoteDraftStatus.FAILED:
                failed += 1
        except Exception:
            failed += 1
            logger.exception("Error driving quote draft for summary %s", s.id)
    return {"processed": processed, "skipped": skipped, "failed": failed}
