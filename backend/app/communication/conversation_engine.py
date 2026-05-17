"""Multi-turn SMS conversation engine.

When an inbound SMS arrives from a known contact, classify the message
state via Claude Haiku and either reply, send a brief close-out, or
stay silent. Loop guard: max 6 auto-replies per conversation.

Architecture pattern ported from Arivio's continue.ts state machine.
Adapted to the FastAPI/SQLAlchemy stack.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.communication.models import SmsMessage, TwilioPhoneNumber
from app.config import Settings
from app.contacts.models import Contact

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 400
MAX_AUTO_REPLIES_PER_CONVERSATION = 6
LOOKBACK_MESSAGES = 20
BURST_DEBOUNCE_SECONDS = 30

SYSTEM_PROMPT = """You are an SMS auto-reply assistant working on behalf of \
a user. You see the last messages of a conversation between the user and a \
contact. The latest inbound message just arrived. Decide what to do:

- "respond": substantive reply (<=2 sentences), keep it natural, match the \
  user's voice/tone from their template + instructions
- "close_out": the conversation is naturally wrapping (caller said thanks, \
  ok, talk soon, etc.). Send a brief acknowledgment + sign-off
- "silent": the previous auto-reply already contained a close phrase \
  ("I'll be in touch", "Talk soon"), OR the inbound message doesn't \
  warrant a reply (one-word ack, automated message, etc.)

Output STRICT JSON only, no markdown, no prose:
{ "action": "respond" | "close_out" | "silent", "draft_text": "<the SMS to send, if action != silent>" }

Keep draft_text under 320 chars. NO emojis unless the user's instructions \
explicitly say so. Match the user's voice."""


def _build_user_prompt(
    user: User, contact: Contact | None, history: list[SmsMessage]
) -> str:
    parts: list[str] = []
    parts.append("USER VOICE TEMPLATE:")
    parts.append(user.conversation_template or "(no template — use neutral friendly tone)")
    if user.conversation_ai_instructions:
        parts.append("\nADDITIONAL TONE INSTRUCTIONS:")
        parts.append(user.conversation_ai_instructions)
    if contact:
        parts.append("\nCONTACT:")
        parts.append(
            f"Name: {contact.contact_name or '(no name)'}, "
            f"Company: {contact.company_name or '(none)'}"
        )
    parts.append("\nMESSAGE HISTORY (oldest first):")
    for m in history:
        who = "them" if m.direction == "inbound" else (
            "you (auto-reply)" if m.is_auto_reply else "you (manual)"
        )
        parts.append(f"[{who}] {(m.body or '')[:300]}")
    parts.append("\nClassify and respond to the latest inbound message.")
    return "\n".join(parts)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def classify_and_respond(
    contact_id: uuid.UUID,
    user_id: uuid.UUID,
    latest_inbound_sms_id: uuid.UUID,
    session_factory,
) -> None:
    """Fire-and-forget: load context, classify, optionally send reply.

    Triggered after inbound SMS persistence in the sms_webhook handler.
    Never raises — failures logged.
    """
    logger.info(
        "conversation_engine.fired contact_id=%s sms_id=%s",
        contact_id, latest_inbound_sms_id,
    )
    try:
        async with session_factory() as db:
            # Resolve user + contact + history
            user_row = await db.execute(select(User).where(User.id == user_id))
            user = user_row.scalar_one_or_none()
            if user is None:
                return
            if not user.conversation_reply_enabled:
                logger.info(
                    "conversation_engine.skipped_user_disabled user_id=%s", user_id
                )
                return
            if not (user.conversation_template or "").strip():
                logger.info(
                    "conversation_engine.skipped_no_template user_id=%s", user_id
                )
                return

            contact_row = await db.execute(
                select(Contact).where(Contact.id == contact_id)
            )
            contact = contact_row.scalar_one_or_none()
            if contact is None:
                logger.info(
                    "conversation_engine.skipped_no_contact contact_id=%s", contact_id
                )
                return

            # Per-contact toggle: NULL = inherit user default (enabled at this
            # point because user.conversation_reply_enabled is true).
            # False = explicit per-contact opt-out.
            if contact.conversation_engine_enabled is False:
                logger.info(
                    "conversation_engine.skipped_contact_disabled contact_id=%s",
                    contact_id,
                )
                return

            # Pause window — set when user manually replies. Expires after 24hr.
            if (
                contact.conversation_engine_paused_until is not None
                and contact.conversation_engine_paused_until.replace(
                    tzinfo=timezone.utc
                    if contact.conversation_engine_paused_until.tzinfo is None
                    else contact.conversation_engine_paused_until.tzinfo
                )
                > datetime.now(timezone.utc)
            ):
                logger.info(
                    "conversation_engine.skipped_paused contact_id=%s until=%s",
                    contact_id, contact.conversation_engine_paused_until,
                )
                return

            # Load last N messages, oldest first
            hist_rows = await db.execute(
                select(SmsMessage)
                .where(SmsMessage.contact_id == contact_id)
                .order_by(SmsMessage.created_at.desc())
                .limit(LOOKBACK_MESSAGES)
            )
            history = list(reversed(list(hist_rows.scalars().all())))
            if not history:
                return

            # Loop guard: count auto-replies in this thread
            auto_count = sum(1 for m in history if m.is_auto_reply)
            if auto_count >= MAX_AUTO_REPLIES_PER_CONVERSATION:
                logger.warning(
                    "conversation_engine.loop_cap_hit contact_id=%s count=%d",
                    contact_id, auto_count,
                )
                return

            # Burst debounce: if last outbound was <30s ago, skip
            last_out = next(
                (m for m in reversed(history) if m.direction == "outbound"), None
            )
            if last_out is not None:
                ts = last_out.created_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - ts < timedelta(
                    seconds=BURST_DEBOUNCE_SECONDS
                ):
                    logger.info(
                        "conversation_engine.skipped_burst_debounce contact_id=%s",
                        contact_id,
                    )
                    return

            user_prompt = _build_user_prompt(user, contact, history)
            user_phone_row = await db.execute(
                select(TwilioPhoneNumber).where(
                    TwilioPhoneNumber.assigned_user_id == user.id
                )
            )
            user_phone = user_phone_row.scalar_one_or_none()
            if user_phone is None:
                logger.warning(
                    "conversation_engine.skipped_no_assigned_number user_id=%s",
                    user_id,
                )
                return

            from_number = user_phone.phone_number
            # Reply target: the inbound sender (i.e., the contact)
            latest_inbound = next(
                (m for m in reversed(history) if m.direction == "inbound"), None
            )
            if latest_inbound is None:
                return
            to_number = latest_inbound.from_number
            contact_id_snap = contact.id
            user_id_snap = user.id

        # ── End of DB scope — call Claude outside the session
        settings = Settings()
        if not settings.anthropic_api_key:
            logger.warning("conversation_engine.skipped_no_anthropic_key")
            return

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=30.0,
            )
            raw = "".join(
                b.text for b in response.content
                if getattr(b, "type", "") == "text"
            )
            parsed = json.loads(_strip_fences(raw))
        except Exception as e:
            logger.warning(
                "conversation_engine.claude_failed contact_id=%s error=%s",
                contact_id, str(e)[:200],
            )
            return

        action = parsed.get("action")
        if action == "silent":
            logger.info(
                "conversation_engine.classified_silent contact_id=%s", contact_id
            )
            return

        draft = (parsed.get("draft_text") or "").strip()[:1600]
        if not draft:
            logger.warning(
                "conversation_engine.empty_draft contact_id=%s action=%s",
                contact_id, action,
            )
            return

        # ── Send the SMS
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("conversation_engine.skipped_twilio_not_configured")
            return

        try:
            from twilio.rest import Client
            twilio_client = Client(
                settings.twilio_account_sid, settings.twilio_auth_token
            )
            tw_msg = twilio_client.messages.create(
                body=draft, from_=from_number, to=to_number
            )
            send_status = "sent"
            twilio_sid = tw_msg.sid
        except Exception as e:
            logger.error(
                "conversation_engine.twilio_send_failed contact_id=%s error=%s",
                contact_id, str(e)[:200],
            )
            send_status = "failed"
            twilio_sid = None

        # Persist as is_auto_reply=true
        async with session_factory() as db:
            sms_row = SmsMessage(
                id=uuid.uuid4(),
                user_id=user_id_snap,
                contact_id=contact_id_snap,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                body=draft,
                status=send_status,
                twilio_sid=twilio_sid,
                is_auto_reply=True,
            )
            db.add(sms_row)
            await db.commit()

            from app.contacts.ai_brief import invalidate_brief_cache
            await invalidate_brief_cache(db, contact_id_snap)

        logger.info(
            "conversation_engine.replied contact_id=%s action=%s chars=%d",
            contact_id, action, len(draft),
        )

        # On close_out: extract memory from the now-completed thread
        if action == "close_out":
            try:
                from app.communication.memory_writer import (
                    write_memory_from_sms_thread_task,
                )
                await write_memory_from_sms_thread_task(
                    contact_id_snap, user_id_snap, session_factory
                )
            except Exception as e:
                logger.warning(
                    "conversation_engine.close_out_memory_failed contact_id=%s "
                    "error=%s",
                    contact_id, str(e)[:200],
                )
    except Exception as e:
        logger.error(
            "conversation_engine.task_failure contact_id=%s error=%s",
            contact_id, str(e)[:300], exc_info=True,
        )


async def pause_for_manual_reply(
    db: AsyncSession, contact_id: uuid.UUID, hours: int = 24
) -> None:
    """When the user manually sends an outbound SMS to a contact, pause
    the conversation engine for that contact. They're talking — AI steps
    back. Default 24hr pause."""
    if contact_id is None:
        return
    row = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = row.scalar_one_or_none()
    if contact is None:
        return
    contact.conversation_engine_paused_until = (
        datetime.now(timezone.utc) + timedelta(hours=hours)
    )
    await db.commit()
    logger.info(
        "conversation_engine.paused_for_manual contact_id=%s hours=%d",
        contact_id, hours,
    )
