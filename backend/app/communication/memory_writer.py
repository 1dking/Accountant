"""Write contact memory rows from various sources.

Triggered as fire-and-forget BackgroundTasks. Never raises — failures
are logged so the originating webhook always succeeds even if memory
extraction has a hiccup.
"""

import logging
import uuid

from sqlalchemy import select

from app.communication.memory_extraction import extract_memory
from app.communication.models import CallLog, SmsMessage
from app.contacts.models import ContactMemory

logger = logging.getLogger(__name__)


async def write_memory_from_voicemail_task(
    call_log_id: uuid.UUID,
    session_factory,
) -> None:
    """Fire-and-forget: extract memory from a completed voicemail
    transcript and write a contact_memories row.

    Skipped if call_logs.contact_id is NULL (no contact to attach to).
    Skipped if transcript is empty.
    """
    logger.info("memory_write.fired call_log_id=%s source=voicemail", call_log_id)
    try:
        async with session_factory() as db:
            row = await db.execute(select(CallLog).where(CallLog.id == call_log_id))
            call_log = row.scalar_one_or_none()
            if call_log is None:
                logger.warning("memory_write.skipped row_gone call_log_id=%s", call_log_id)
                return
            if call_log.contact_id is None:
                logger.info(
                    "memory_write.skipped_no_contact call_log_id=%s", call_log_id
                )
                return
            if not (call_log.voicemail_transcript or "").strip():
                logger.info(
                    "memory_write.skipped_empty_transcript call_log_id=%s", call_log_id
                )
                return

            caller_context = (
                f"Voicemail left by {call_log.from_number} on {call_log.created_at}"
            )
            extracted = await extract_memory(
                raw_text=call_log.voicemail_transcript,
                source_type="voicemail",
                caller_context=caller_context,
            )

            memory = ContactMemory(
                id=uuid.uuid4(),
                contact_id=call_log.contact_id,
                user_id=call_log.user_id,
                source_type="voicemail",
                source_id=call_log.id,
                summary=extracted["summary"],
                commitments=extracted["commitments"],
                cares_about=extracted["cares_about"],
                talking_points=extracted["talking_points"],
                raw_input=call_log.voicemail_transcript,
            )
            db.add(memory)
            await db.commit()

        logger.info(
            "memory_write.task_success call_log_id=%s memory_id=%s",
            call_log_id, memory.id,
        )
    except Exception as e:
        logger.error(
            "memory_write.task_failure call_log_id=%s error=%s",
            call_log_id, str(e)[:300], exc_info=True,
        )


async def write_memory_from_sms_thread_task(
    contact_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory,
    lookback_messages: int = 20,
) -> None:
    """Fire-and-forget: extract memory from the recent SMS thread with a
    contact. Pulls the last N messages (both directions) and runs extraction
    over the concatenated thread.
    """
    logger.info(
        "memory_write.fired contact_id=%s source=sms_thread", contact_id
    )
    try:
        async with session_factory() as db:
            rows = await db.execute(
                select(SmsMessage)
                .where(SmsMessage.contact_id == contact_id)
                .order_by(SmsMessage.created_at.desc())
                .limit(lookback_messages)
            )
            messages = list(rows.scalars().all())
            if not messages:
                logger.info(
                    "memory_write.skipped_empty_thread contact_id=%s", contact_id
                )
                return

            messages.reverse()  # oldest first for context
            thread = "\n".join(
                f"[{m.direction}] {m.body}" for m in messages if m.body
            )

            extracted = await extract_memory(
                raw_text=thread,
                source_type="sms_thread",
            )

            memory = ContactMemory(
                id=uuid.uuid4(),
                contact_id=contact_id,
                user_id=user_id,
                source_type="sms_thread",
                source_id=None,
                summary=extracted["summary"],
                commitments=extracted["commitments"],
                cares_about=extracted["cares_about"],
                talking_points=extracted["talking_points"],
                raw_input=thread,
            )
            db.add(memory)
            await db.commit()

        logger.info(
            "memory_write.task_success contact_id=%s memory_id=%s source=sms_thread",
            contact_id, memory.id,
        )
    except Exception as e:
        logger.error(
            "memory_write.task_failure contact_id=%s source=sms_thread error=%s",
            contact_id, str(e)[:300], exc_info=True,
        )
