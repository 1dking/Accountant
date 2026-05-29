"""Meeting transcription pipeline — AssemblyAI integration (Commit 11).

Flow:
  1. handle_egress_completion calls submit_meeting_transcription when
     a recording transitions to AVAILABLE.
  2. We generate a presigned R2 URL for the recording (1-hour TTL),
     POST it to AssemblyAI with speaker_labels=true. AssemblyAI returns
     a transcript_id immediately — we don't block.
  3. We persist a RecordingTranscript row in PROCESSING state with the
     transcript_id stamped on provider_id.
  4. A scheduler job (poll_pending_transcriptions, every 2 min) iterates
     PROCESSING rows, polls AssemblyAI for each, and finalizes any that
     have completed.

Cost model: ~$0.49/hr of recording at the nano tier with speaker
diarization (Best tier). Submitted on every successful egress; skipped
when no AssemblyAI key is configured (dev boxes, tests).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.meetings.models import (
    MeetingRecording, RecordingTranscript, TranscriptStatus,
)

logger = logging.getLogger(__name__)

_ASSEMBLY_BASE = "https://api.assemblyai.com/v2"


# ---------------------------------------------------------------------------
# R2 presigned-URL helper
# ---------------------------------------------------------------------------


def _generate_presigned_url(
    settings: Settings, key: str, expires_in: int = 3600,
) -> str:
    """Generate a 1-hour presigned R2 (S3-compatible) GET URL.

    AssemblyAI fetches the audio directly from this URL — avoids us
    streaming hundreds of MB of MP4 through the backend.
    """
    import boto3
    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def submit_meeting_transcription(
    db: AsyncSession,
    recording: MeetingRecording,
    settings: Settings,
) -> RecordingTranscript | None:
    """Kick off AssemblyAI transcription for a completed recording.

    Idempotent — if a transcript row already exists for this recording
    in any non-FAILED state, returns it unchanged. Returns None when
    AssemblyAI isn't configured (dev box) or when the recording lacks
    a storage_path (defensive — shouldn't happen post-egress).
    """
    if not recording.storage_path:
        logger.warning(
            "meeting.transcription_skipped recording_id=%s reason=no_storage_path",
            recording.id,
        )
        return None
    if not settings.assemblyai_api_key:
        logger.info(
            "meeting.transcription_skipped recording_id=%s reason=no_api_key",
            recording.id,
        )
        return None
    if not (settings.r2_access_key_id and settings.r2_bucket_name):
        logger.info(
            "meeting.transcription_skipped recording_id=%s reason=no_r2_config",
            recording.id,
        )
        return None

    # Idempotency check — don't re-submit if there's already a row.
    existing = await db.execute(
        select(RecordingTranscript).where(
            RecordingTranscript.recording_id == recording.id,
        )
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row is not None and existing_row.status != TranscriptStatus.FAILED:
        return existing_row

    # Build presigned URL + POST to AssemblyAI. The presign call is
    # synchronous boto3, so off-thread it to keep the event loop free.
    try:
        audio_url = await asyncio.to_thread(
            _generate_presigned_url, settings, recording.storage_path,
        )
    except Exception as exc:
        logger.warning(
            "meeting.transcription_presign_failed recording_id=%s err=%s",
            recording.id, str(exc)[:200],
        )
        return None

    headers = {"authorization": settings.assemblyai_api_key}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_ASSEMBLY_BASE}/transcript",
                headers=headers,
                json={
                    "audio_url": audio_url,
                    "speech_models": ["universal-3-pro"],
                    "speaker_labels": True,
                    "punctuate": True,
                    "format_text": True,
                },
            )
            resp.raise_for_status()
            transcript_id = resp.json()["id"]
    except Exception as exc:
        logger.warning(
            "meeting.transcription_submit_failed recording_id=%s err=%s",
            recording.id, str(exc)[:300],
        )
        return None

    # Persist a fresh PROCESSING row (or update FAILED → PROCESSING on retry).
    if existing_row is not None and existing_row.status == TranscriptStatus.FAILED:
        existing_row.status = TranscriptStatus.PROCESSING
        existing_row.provider_id = transcript_id
        existing_row.error_message = None
        await db.commit()
        await db.refresh(existing_row)
        logger.info(
            "meeting.transcription_resubmitted recording_id=%s transcript_id=%s",
            recording.id, transcript_id,
        )
        return existing_row

    row = RecordingTranscript(
        meeting_id=recording.meeting_id,
        recording_id=recording.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai",
        provider_id=transcript_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "meeting.transcription_submitted recording_id=%s transcript_id=%s",
        recording.id, transcript_id,
    )
    return row


async def _poll_one(
    db: AsyncSession, row: RecordingTranscript, settings: Settings,
) -> bool:
    """Poll a single PROCESSING transcript. Returns True if a state
    change happened (AVAILABLE or FAILED), False if still processing."""
    if not row.provider_id or not settings.assemblyai_api_key:
        return False
    headers = {"authorization": settings.assemblyai_api_key}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_ASSEMBLY_BASE}/transcript/{row.provider_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "meeting.transcription_poll_failed transcript_id=%s err=%s",
            row.provider_id, str(exc)[:200],
        )
        return False

    aai_status = data.get("status")
    if aai_status == "completed":
        segments = []
        for utt in (data.get("utterances") or []):
            segments.append({
                "start": int(utt.get("start", 0)) / 1000.0,
                "end": int(utt.get("end", 0)) / 1000.0,
                "text": utt.get("text", ""),
                "speaker": utt.get("speaker", "?"),
            })
        row.status = TranscriptStatus.AVAILABLE
        row.full_text = data.get("text") or ""
        row.segments_json = segments
        row.language = data.get("language_code")
        if data.get("audio_duration"):
            row.duration_seconds = int(data["audio_duration"])
        await db.commit()
        logger.info(
            "meeting.transcription_completed transcript_id=%s segments=%d",
            row.provider_id, len(segments),
        )
        # Commit 12 — kick off Claude summary now that the transcript
        # is available. Best-effort: failure here doesn't roll back
        # the transcript completion. The scheduler will re-drive any
        # missed summaries on its tick.
        try:
            from app.meetings.summarization import submit_summary
            await submit_summary(db, row, settings)
        except Exception as exc:
            logger.warning(
                "meeting.summary_kickoff_failed transcript_id=%s err=%s",
                row.id, str(exc)[:200],
            )
        return True

    if aai_status == "error":
        # AssemblyAI returns errors for silent audio too. Treat
        # "no spoken audio" as an empty-but-valid transcript instead of
        # a failure (matches the brain transcription path's convention).
        err_msg = (data.get("error") or "").lower()
        if "no spoken audio" in err_msg or "language detection" in err_msg:
            row.status = TranscriptStatus.AVAILABLE
            row.full_text = ""
            row.segments_json = []
            await db.commit()
            logger.info(
                "meeting.transcription_empty_audio transcript_id=%s",
                row.provider_id,
            )
            return True
        row.status = TranscriptStatus.FAILED
        row.error_message = (data.get("error") or "Unknown")[:500]
        await db.commit()
        logger.warning(
            "meeting.transcription_failed transcript_id=%s err=%s",
            row.provider_id, row.error_message,
        )
        return True

    return False


async def poll_pending_transcriptions(
    db: AsyncSession, settings: Settings, *, batch_limit: int = 10,
) -> dict:
    """Scheduler entry point — drive any PROCESSING rows forward.

    Returns {polled, completed, failed} for observability. Idempotent:
    safe to overlap; the per-row poll is read-mostly until completion.
    """
    if not settings.assemblyai_api_key:
        return {"polled": 0, "completed": 0, "failed": 0}
    rows = await db.execute(
        select(RecordingTranscript)
        .where(RecordingTranscript.status == TranscriptStatus.PROCESSING)
        .limit(batch_limit)
    )
    pending = list(rows.scalars().all())
    completed = 0
    failed = 0
    for row in pending:
        changed = await _poll_one(db, row, settings)
        if changed:
            if row.status == TranscriptStatus.AVAILABLE:
                completed += 1
            elif row.status == TranscriptStatus.FAILED:
                failed += 1
    return {"polled": len(pending), "completed": completed, "failed": failed}
