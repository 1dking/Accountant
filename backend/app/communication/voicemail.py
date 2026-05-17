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

        # Chain memory extraction after transcript lands. Fire-and-forget.
        # write_memory_from_voicemail_task skips internally if contact_id is NULL.
        try:
            from app.communication.memory_writer import write_memory_from_voicemail_task
            import asyncio
            asyncio.create_task(
                write_memory_from_voicemail_task(call_log_id, session_factory)
            )
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
