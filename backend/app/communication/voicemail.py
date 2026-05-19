"""Voicemail post-processing — fire-and-forget transcription via AssemblyAI.

This module exists separately from communication.service to keep the heavy
brain.transcription_service import lazy: we only pay the import cost when a
voicemail is actually transcribed (~1/day in practice), not on every webhook.

The task is wired up by /voice/voicemail-status via FastAPI BackgroundTasks.
Never raises — on any failure it marks voicemail_transcript_status='failed'
so the UI can show a clear state and a future periodic worker can re-process.
"""

import logging
import uuid

import httpx
from sqlalchemy import select

from app.communication.models import CallLog

logger = logging.getLogger(__name__)

# Recordings under this duration almost always come back from AssemblyAI as
# empty text or hard-fail (the 2026-05-16 voicemail batch had 5 of 7
# recordings at 1-2 seconds, all failed). Skip them at the task door so the
# AssemblyAI bill + log noise both drop, and the UI gets a clear status
# instead of a useless "failed".
MIN_TRANSCRIBE_DURATION_SECONDS = 3


async def transcribe_voicemail_task(
    call_log_id: uuid.UUID,
    recording_sid: str,
    account_sid: str,
    auth_token: str,
    session_factory,
) -> None:
    """Download voicemail recording from Twilio, transcribe via AssemblyAI,
    persist transcript on the call_logs row.

    Fire-and-forget. Opens its own DB session via session_factory (the
    request-scoped session that scheduled this task is already closed).
    """
    logger.info(
        "voicemail_transcribe.task_start call_log_id=%s recording_sid=%s",
        call_log_id, recording_sid,
    )
    try:
        # 0. Duration gate. If the row already has a duration < 3s,
        # skip AssemblyAI entirely — it would return empty text or
        # 400 anyway. NULL duration falls through (defensive — better
        # to attempt + fail than block on a missing field).
        async with session_factory() as db:
            row = await db.execute(
                select(CallLog).where(CallLog.id == call_log_id)
            )
            call_log = row.scalar_one_or_none()
            if call_log is None:
                logger.warning(
                    "voicemail_transcribe.task_aborted row gone call_log_id=%s",
                    call_log_id,
                )
                return
            duration = call_log.recording_duration_seconds
            if duration is not None and duration < MIN_TRANSCRIBE_DURATION_SECONDS:
                call_log.voicemail_transcript_status = "too_short"
                call_log.voicemail_transcript = None
                await db.commit()
                logger.info(
                    "voicemail_transcribe.too_short call_log_id=%s duration=%ds "
                    "(skipped AssemblyAI; no memory chain)",
                    call_log_id, duration,
                )
                return

        # 1. Fetch recording bytes from Twilio (Account-SID Basic Auth)
        twilio_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}"
            f"/Recordings/{recording_sid}.mp3"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(twilio_url, auth=(account_sid, auth_token))
            resp.raise_for_status()
            audio_bytes = resp.content

        # 2. Transcribe via AssemblyAI (reuse existing battle-tested helper)
        from app.brain.transcription_service import transcribe_with_assemblyai
        result = await transcribe_with_assemblyai(audio_bytes)
        transcript_text = (result.get("text") or "").strip()

        # 3. Persist — open our own session, the request's is long-closed
        async with session_factory() as db:
            row = await db.execute(
                select(CallLog).where(CallLog.id == call_log_id)
            )
            call_log = row.scalar_one_or_none()
            if call_log is None:
                logger.warning(
                    "voicemail_transcribe.task_failure row gone call_log_id=%s",
                    call_log_id,
                )
                return
            call_log.voicemail_transcript = transcript_text
            call_log.voicemail_transcript_status = "completed"
            await db.commit()

        logger.info(
            "voicemail_transcribe.task_success call_log_id=%s chars=%d",
            call_log_id, len(transcript_text),
        )

        # Chain memory extraction after transcript lands. We're already
        # in a background task — awaiting inline is reliable (no request
        # context here for FastAPI's BackgroundTasks). The ~1-2s added
        # latency only delays the next free moment of this background
        # task, not any user-facing response.
        try:
            from app.communication.memory_writer import write_memory_from_voicemail_task
            await write_memory_from_voicemail_task(call_log_id, session_factory)
        except Exception as e:
            logger.warning(
                "voicemail_transcribe.memory_chain_failed call_log_id=%s error=%s",
                call_log_id, str(e)[:200],
            )
    except Exception as e:
        logger.error(
            "voicemail_transcribe.task_failure call_log_id=%s error=%s",
            call_log_id, str(e)[:300],
            exc_info=True,
        )
        # Mark row failed so UI doesn't spin forever and future recovery
        # worker can pick it up.
        try:
            async with session_factory() as db:
                row = await db.execute(
                    select(CallLog).where(CallLog.id == call_log_id)
                )
                call_log = row.scalar_one_or_none()
                if call_log is not None:
                    call_log.voicemail_transcript_status = "failed"
                    await db.commit()
        except Exception as inner:
            logger.error(
                "voicemail_transcribe.failure_mark_failed call_log_id=%s error=%s",
                call_log_id, str(inner)[:300],
            )
