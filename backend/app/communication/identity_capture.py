"""Unknown-caller identity capture flow.

State machine triggered by classify_and_respond when an inbound SMS
arrives from a phone NOT in contacts AND the engine is enabled.

States (derived from identity_capture_attempts row + sms history):
  - first_contact: no prior attempt → AI sends "who is this?"
  - expecting_answer: AI asked once → next inbound is the answer
  - exhausted: 2 failed attempts within 7d → stop pestering
  - succeeded: contact_created_id is set → engine resumes normal flow

The model + extraction helper live here. classify_and_respond branches
to identity_capture_flow() before the normal classifier runs.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic
from sqlalchemy import Boolean, CHAR, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.database import Base

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_ATTEMPTS_PER_7_DAYS = 2
RATE_LIMIT_WINDOW = timedelta(days=7)


class IdentityCaptureAttempt(Base):
    """Per (phone, user) record of an identity-capture exchange."""
    __tablename__ = "identity_capture_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    first_inbound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    asked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extracted_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Logical reference to contacts.id — SQLite ALTER constraint limits.
    contact_created_id: Mapped[uuid.UUID | None] = mapped_column(
        CHAR(32), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


EXTRACTION_SYSTEM_PROMPT = """You extract a person's name and (optionally) \
email address from a single SMS reply. The SMS was sent in response to \
"What's your name and email?". Return JSON ONLY, no prose:

{ "name": "<full name>" or null, "email": "<email>" or null, "confidence": "high"|"low"|"none" }

Rules:
- confidence="high": the message clearly answers with a name (and \
optionally email). Example: "It's Sarah from Bensimon, sarah@bb.ca"
- confidence="low": ambiguous answer that might contain a name but \
unclear. Example: "Hi" or "this is me"
- confidence="none": the reply doesn't answer the question at all. \
Example: "What's up?" or "tomorrow at 2pm" — they ignored the ask
- Strip greetings from the name ("Hi I'm Sarah" → "Sarah").
- If only first name given, use that. Don't invent last names.
- Email must look like a real address (contain @ and a dot in domain). \
Otherwise null."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_identity(reply_text: str) -> dict:
    """Run Claude extraction on an SMS reply. Returns
    { name, email, confidence } with confidence='none' on failure."""
    settings = Settings()
    if not settings.anthropic_api_key:
        return {"name": None, "email": None, "confidence": "none"}
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": reply_text}],
            timeout=20.0,
        )
        raw = "".join(
            b.text for b in response.content if getattr(b, "type", "") == "text"
        )
        parsed = json.loads(_strip_fences(raw))
        return {
            "name": (parsed.get("name") or None),
            "email": (parsed.get("email") or None),
            "confidence": parsed.get("confidence") or "none",
        }
    except Exception as e:
        logger.warning("identity_capture.extract_failed error=%s", str(e)[:200])
        return {"name": None, "email": None, "confidence": "none"}


async def get_or_create_attempt(
    db: AsyncSession,
    phone_number: str,
    user_id: uuid.UUID,
    first_inbound_at: datetime,
) -> tuple["IdentityCaptureAttempt", bool]:
    """Return (attempt_row, is_new). Looks up existing row by
    (phone_number, user_id) — unique index protects this."""
    from sqlalchemy import select

    row = await db.execute(
        select(IdentityCaptureAttempt).where(
            IdentityCaptureAttempt.phone_number == phone_number,
            IdentityCaptureAttempt.user_id == user_id,
        )
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        return existing, False

    attempt = IdentityCaptureAttempt(
        id=uuid.uuid4(),
        phone_number=phone_number,
        user_id=user_id,
        first_inbound_at=first_inbound_at,
        attempt_count=0,  # bumped to 1 when ask is sent
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt, True


def is_rate_limited(attempt: IdentityCaptureAttempt) -> bool:
    """True if 2+ attempts have happened in the last 7 days AND the
    last attempt is unanswered. Doesn't block re-engagement on truly
    old numbers — gates only the active back-off window."""
    if attempt.attempt_count < MAX_ATTEMPTS_PER_7_DAYS:
        return False
    if attempt.answered_at is not None:
        return False  # already resolved
    last = attempt.last_attempt_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last) < RATE_LIMIT_WINDOW


def determine_state(
    attempt: IdentityCaptureAttempt, just_created: bool
) -> str:
    """One of: 'first_contact' | 'expecting_answer' | 'exhausted' | 'succeeded'."""
    if attempt.contact_created_id is not None or attempt.answered_at is not None:
        return "succeeded"
    if is_rate_limited(attempt):
        return "exhausted"
    if just_created or attempt.asked_at is None:
        return "first_contact"
    return "expecting_answer"


# ── Outbound copy ─────────────────────────────────────────────────────

FIRST_ASK = (
    "Hey, thanks for texting! I don't have your contact info — could "
    "you share your name (and email if you have a moment)? I'll get "
    "back to you properly once I know who I'm speaking to."
)

CLARIFY_ASK = (
    "Sorry, I didn't catch your name. Could you reply with your name "
    "and email like 'I'm John, john@example.com'?"
)

CONFIRMATION_TEMPLATE = "Thanks {name}! I've got you in my system. I'll follow up soon."


async def handle_unknown_sms_task(
    sms_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory,
) -> None:
    """Fire-and-forget identity-capture orchestrator.

    Triggered from sms_webhook when an inbound SMS arrives with
    contact_id=NULL AND the user has conversation_reply_enabled AND
    identity_capture_enabled.

    Never raises — all failures logged.
    """
    logger.info("identity_capture.fired sms_id=%s user_id=%s", sms_id, user_id)
    try:
        from sqlalchemy import select
        from app.auth.models import User
        from app.communication.models import SmsMessage, TwilioPhoneNumber

        async with session_factory() as db:
            sms_row = await db.execute(select(SmsMessage).where(SmsMessage.id == sms_id))
            sms = sms_row.scalar_one_or_none()
            if sms is None:
                return
            if sms.direction != "inbound":
                return

            user_row = await db.execute(select(User).where(User.id == user_id))
            user = user_row.scalar_one_or_none()
            if user is None or not user.conversation_reply_enabled:
                logger.info(
                    "identity_capture.skipped_engine_off user_id=%s", user_id
                )
                return
            if not getattr(user, "identity_capture_enabled", True):
                logger.info(
                    "identity_capture.skipped_capture_disabled user_id=%s", user_id
                )
                return

            from_number = sms.from_number
            inbound_body = sms.body or ""

            attempt, is_new = await get_or_create_attempt(
                db, from_number, user_id, sms.created_at or datetime.now(timezone.utc)
            )
            state = determine_state(attempt, is_new)
            logger.info(
                "identity_capture.state phone=%s state=%s attempt_count=%d",
                from_number, state, attempt.attempt_count,
            )

            if state == "exhausted":
                logger.warning(
                    "identity_capture.exhausted phone=%s attempts=%d",
                    from_number, attempt.attempt_count,
                )
                return

            if state == "succeeded":
                # Defensive — shouldn't reach here if contact_id was matched
                # upstream. Backfill the current SMS row's contact_id and
                # exit so the normal engine picks up next inbound.
                if attempt.contact_created_id is not None:
                    sms.contact_id = attempt.contact_created_id
                    await db.commit()
                return

            # Resolve the user's assigned Twilio number to send FROM
            phone_row = await db.execute(
                select(TwilioPhoneNumber).where(
                    TwilioPhoneNumber.assigned_user_id == user_id
                )
            )
            phone = phone_row.scalar_one_or_none()
            if phone is None:
                logger.warning(
                    "identity_capture.skipped_no_assigned_number user_id=%s",
                    user_id,
                )
                return
            from_twilio = phone.phone_number

            if state == "first_contact":
                await _send_capture_ask(
                    db, user_id, from_twilio, from_number, FIRST_ASK, attempt
                )
                return

            # state == 'expecting_answer'
            extraction = await extract_identity(inbound_body)
            confidence = extraction.get("confidence", "none")
            name = extraction.get("name")
            email = extraction.get("email")

            if confidence == "high" and name:
                await _on_identity_extracted(
                    db, user_id, from_twilio, from_number,
                    name=name, email=email, attempt=attempt,
                    first_inbound_at=attempt.first_inbound_at,
                )
                return

            # Low or none — clarify, increment attempt
            if attempt.attempt_count >= MAX_ATTEMPTS_PER_7_DAYS:
                # Already at the cap — don't ask a third time
                logger.warning(
                    "identity_capture.exhausted_after_clarify phone=%s",
                    from_number,
                )
                await _on_capture_failed(db, user_id, from_number, attempt)
                return

            await _send_capture_ask(
                db, user_id, from_twilio, from_number, CLARIFY_ASK, attempt
            )

    except Exception as e:
        logger.error(
            "identity_capture.task_failure sms_id=%s error=%s",
            sms_id, str(e)[:300], exc_info=True,
        )


async def _send_capture_ask(
    db: AsyncSession,
    user_id: uuid.UUID,
    from_twilio: str,
    to_unknown: str,
    body: str,
    attempt: IdentityCaptureAttempt,
) -> None:
    """Send the identity-capture SMS via Twilio + persist as
    is_identity_capture_attempt=true. Bump attempt counter."""
    from app.communication.models import SmsMessage
    from app.notifications.service import create_notification

    settings = Settings()
    sent_status = "failed"
    twilio_sid = None
    if settings.twilio_account_sid and settings.twilio_auth_token:
        try:
            from twilio.rest import Client
            twilio_client = Client(
                settings.twilio_account_sid, settings.twilio_auth_token
            )
            tw_msg = twilio_client.messages.create(
                body=body, from_=from_twilio, to=to_unknown
            )
            sent_status = "sent"
            twilio_sid = tw_msg.sid
        except Exception as e:
            logger.error(
                "identity_capture.send_failed phone=%s error=%s",
                to_unknown, str(e)[:200],
            )

    row = SmsMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        contact_id=None,
        direction="outbound",
        from_number=from_twilio,
        to_number=to_unknown,
        body=body[:1600],
        status=sent_status,
        twilio_sid=twilio_sid,
        is_auto_reply=True,
        is_identity_capture_attempt=True,
    )
    db.add(row)

    attempt.asked_at = datetime.now(timezone.utc)
    attempt.last_attempt_at = datetime.now(timezone.utc)
    attempt.attempt_count = (attempt.attempt_count or 0) + 1
    await db.commit()

    try:
        await create_notification(
            db,
            user_id=user_id,
            type="identity_capture_asked",
            title=f"Asked identity from {to_unknown}",
            message=body[:200],
            resource_type="sms_message",
            resource_id=str(row.id),
            link_path="/communication?tab=sms",
        )
    except Exception as e:
        logger.warning("identity_capture.notify_ask_failed error=%s", str(e)[:200])

    logger.info(
        "identity_capture.asked phone=%s attempt=%d status=%s",
        to_unknown, attempt.attempt_count, sent_status,
    )


async def _on_identity_extracted(
    db: AsyncSession,
    user_id: uuid.UUID,
    from_twilio: str,
    to_unknown: str,
    *,
    name: str,
    email: str | None,
    attempt: IdentityCaptureAttempt,
    first_inbound_at: datetime,
) -> None:
    """Create the contact, backfill SMS thread, send confirmation."""
    from sqlalchemy import or_, update
    from app.communication.models import SmsMessage
    from app.contacts.models import Contact, ContactType
    from app.notifications.service import create_notification

    # Strip + dedupe-safe normalization. phone stored without + per
    # existing contacts schema convention; the NANP normalizer in
    # service._strip_non_digits handles both formats on lookup.
    normalized_phone = to_unknown

    contact = Contact(
        id=uuid.uuid4(),
        type=ContactType.CLIENT,
        company_name=name,  # Company is required; default to person name
        contact_name=name,
        email=email,
        phone=normalized_phone,
        country="US",
        is_active=True,
        created_by=user_id,
        assigned_user_id=user_id,
    )
    db.add(contact)
    await db.flush()

    # Backfill all prior sms_messages on this phone with the new contact_id
    await db.execute(
        update(SmsMessage)
        .where(
            or_(
                SmsMessage.from_number == to_unknown,
                SmsMessage.to_number == to_unknown,
            ),
            SmsMessage.contact_id.is_(None),
            SmsMessage.created_at >= first_inbound_at,
        )
        .values(contact_id=contact.id)
    )

    attempt.extracted_name = name
    attempt.extracted_email = email
    attempt.contact_created_id = contact.id
    attempt.answered_at = datetime.now(timezone.utc)
    attempt.last_attempt_at = datetime.now(timezone.utc)
    await db.commit()

    # Send confirmation SMS
    confirmation = CONFIRMATION_TEMPLATE.format(name=name.split()[0])
    settings = Settings()
    if settings.twilio_account_sid and settings.twilio_auth_token:
        try:
            from twilio.rest import Client
            twilio_client = Client(
                settings.twilio_account_sid, settings.twilio_auth_token
            )
            tw_msg = twilio_client.messages.create(
                body=confirmation, from_=from_twilio, to=to_unknown
            )
            confirm_row = SmsMessage(
                id=uuid.uuid4(),
                user_id=user_id,
                contact_id=contact.id,
                direction="outbound",
                from_number=from_twilio,
                to_number=to_unknown,
                body=confirmation,
                status="sent",
                twilio_sid=tw_msg.sid,
                is_auto_reply=True,
            )
            db.add(confirm_row)
            await db.commit()
        except Exception as e:
            logger.error(
                "identity_capture.confirmation_send_failed phone=%s error=%s",
                to_unknown, str(e)[:200],
            )

    try:
        await create_notification(
            db,
            user_id=user_id,
            type="contact_auto_created",
            title=f"New contact captured: {name}",
            message=f"Auto-captured from SMS{f' — {email}' if email else ''}",
            resource_type="contact",
            resource_id=str(contact.id),
            link_path=f"/contacts/{contact.id}",
            contact_id=contact.id,
        )
    except Exception as e:
        logger.warning(
            "identity_capture.notify_contact_created_failed error=%s", str(e)[:200]
        )

    logger.info(
        "identity_capture.succeeded phone=%s contact_id=%s name=%s has_email=%s",
        to_unknown, contact.id, name, bool(email),
    )


async def _on_capture_failed(
    db: AsyncSession,
    user_id: uuid.UUID,
    phone: str,
    attempt: IdentityCaptureAttempt,
) -> None:
    """Notify user that capture failed after max attempts."""
    from app.notifications.service import create_notification

    attempt.last_attempt_at = datetime.now(timezone.utc)
    await db.commit()
    try:
        await create_notification(
            db,
            user_id=user_id,
            type="identity_capture_failed",
            title=f"Couldn't capture identity from {phone}",
            message="Failed after 2 attempts — manual follow-up needed",
            resource_type="identity_capture",
            resource_id=str(attempt.id),
            link_path="/communication?tab=sms",
        )
    except Exception as e:
        logger.warning(
            "identity_capture.notify_failed_send_failed error=%s", str(e)[:200]
        )

