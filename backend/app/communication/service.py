
import json
import re
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.communication.models import (
    CallLog,
    LiveChatMessage,
    LiveChatSession,
    SmsMessage,
    TwilioPhoneNumber,
)
from app.communication.schemas import (
    CallLogCreate,
    LiveChatMessageCreate,
    LiveChatSessionCreate,
    TwilioPhoneNumberCreate,
)
from app.config import Settings
from app.contacts.models import ActivityType, Contact
from app.contacts.service import log_contact_activity
from app.core.exceptions import NotFoundError, ValidationError


def _strip_non_digits(phone: str) -> str:
    """Strip all non-digit characters from a phone number for comparison."""
    return re.sub(r"\D", "", phone)


async def _find_contact_by_phone(db: AsyncSession, phone: str) -> Contact | None:
    """Find a contact by phone number, stripping non-digits for comparison."""
    stripped = _strip_non_digits(phone)
    if not stripped:
        return None
    # Check contacts where stripped phone matches
    result = await db.execute(
        select(Contact).where(Contact.phone.isnot(None))
    )
    for contact in result.scalars().all():
        if contact.phone and _strip_non_digits(contact.phone) == stripped:
            return contact
    return None


def _get_twilio_client(settings: Settings):
    from twilio.rest import Client

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValidationError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


# ---------------------------------------------------------------------------
# Phone Numbers
# ---------------------------------------------------------------------------


async def list_phone_numbers(db: AsyncSession) -> list[TwilioPhoneNumber]:
    result = await db.execute(
        select(TwilioPhoneNumber).order_by(TwilioPhoneNumber.created_at.desc())
    )
    return list(result.scalars().all())


async def add_phone_number(
    db: AsyncSession, data: TwilioPhoneNumberCreate
) -> TwilioPhoneNumber:
    phone = TwilioPhoneNumber(
        id=uuid.uuid4(),
        phone_number=data.phone_number,
        friendly_name=data.friendly_name,
        capabilities_json=data.capabilities_json,
    )
    db.add(phone)
    await db.commit()
    await db.refresh(phone)
    return phone


async def assign_phone_number(
    db: AsyncSession, phone_id: uuid.UUID, user_id: uuid.UUID | None
) -> TwilioPhoneNumber:
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.id == phone_id)
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        raise NotFoundError("TwilioPhoneNumber", str(phone_id))
    phone.assigned_user_id = user_id
    await db.commit()
    await db.refresh(phone)
    return phone


async def delete_phone_number(db: AsyncSession, phone_id: uuid.UUID) -> None:
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.id == phone_id)
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        raise NotFoundError("TwilioPhoneNumber", str(phone_id))
    await db.delete(phone)
    await db.commit()


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


async def create_call_log(
    db: AsyncSession, data: CallLogCreate, user: User
) -> CallLog:
    # Try to match contact by phone number if not provided
    contact_id = data.contact_id
    if not contact_id:
        phone_to_match = (
            data.from_number if data.direction == "inbound" else data.to_number
        )
        contact = await _find_contact_by_phone(db, phone_to_match)
        if contact:
            contact_id = contact.id

    call = CallLog(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact_id,
        direction=data.direction,
        from_number=data.from_number,
        to_number=data.to_number,
        duration_seconds=data.duration_seconds,
        recording_url=data.recording_url,
        status=data.status,
        notes=data.notes,
        outcome=data.outcome,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Log to contact timeline
    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.CALL_LOGGED,
            title=f"{data.direction.capitalize()} call ({data.status})",
            description=data.notes,
            reference_type="call_log",
            reference_id=call.id,
            user_id=user.id,
        )

    return call


async def list_call_logs(
    db: AsyncSession,
    contact_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[CallLog], int]:
    query = select(CallLog)

    if contact_id:
        query = query.where(CallLog.contact_id == contact_id)
    if user_id:
        query = query.where(CallLog.user_id == user_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        query.order_by(CallLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_capability_token(db: AsyncSession, user: User, settings: Settings) -> str:
    """Generate a Twilio capability token for browser-based calling."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValidationError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )

    from twilio.jwt.client import ClientCapabilityToken

    capability = ClientCapabilityToken(
        settings.twilio_account_sid,
        settings.twilio_auth_token,
    )
    # Allow outgoing calls via TwiML app if configured
    capability.allow_client_outgoing(settings.twilio_account_sid)
    # Allow incoming calls to this user's identity
    capability.allow_client_incoming(str(user.id))

    return capability.to_jwt()


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------


async def send_sms(
    db: AsyncSession, user: User, to_number: str, body: str, settings: Settings
) -> SmsMessage:
    """Send an SMS via Twilio and log it."""
    client = _get_twilio_client(settings)

    if not settings.twilio_from_number:
        raise ValidationError(
            "No Twilio phone number configured. Set TWILIO_FROM_NUMBER."
        )

    # Try to match contact by phone number
    contact = await _find_contact_by_phone(db, to_number)
    contact_id = contact.id if contact else None

    try:
        twilio_message = client.messages.create(
            body=body,
            from_=settings.twilio_from_number,
            to=to_number,
        )
        status = "sent"
        sid = twilio_message.sid
    except Exception:
        status = "failed"
        sid = None

    sms = SmsMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact_id,
        direction="outbound",
        from_number=settings.twilio_from_number,
        to_number=to_number,
        body=body[:1600],
        status=status,
        twilio_sid=sid,
    )
    db.add(sms)
    await db.commit()
    await db.refresh(sms)

    # Log to contact timeline
    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.SMS_SENT,
            title="SMS sent",
            description=body[:200],
            reference_type="sms_message",
            reference_id=sms.id,
            user_id=user.id,
        )

    return sms


async def receive_sms(
    db: AsyncSession,
    from_number: str,
    to_number: str,
    body: str,
    twilio_sid: str | None = None,
) -> SmsMessage:
    """Log an incoming SMS received via Twilio webhook."""
    # Match contact by phone number
    contact = await _find_contact_by_phone(db, from_number)
    contact_id = contact.id if contact else None

    sms = SmsMessage(
        id=uuid.uuid4(),
        user_id=None,
        contact_id=contact_id,
        direction="inbound",
        from_number=from_number,
        to_number=to_number,
        body=body[:1600],
        status="received",
        twilio_sid=twilio_sid,
    )
    db.add(sms)
    await db.commit()
    await db.refresh(sms)

    # Log to contact timeline
    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.SMS_RECEIVED,
            title="SMS received",
            description=body[:200],
            reference_type="sms_message",
            reference_id=sms.id,
        )

    return sms


async def list_sms_messages(
    db: AsyncSession,
    contact_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[SmsMessage], int]:
    query = select(SmsMessage)

    if contact_id:
        query = query.where(SmsMessage.contact_id == contact_id)
    if user_id:
        query = query.where(SmsMessage.user_id == user_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        query.order_by(SmsMessage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


# ---------------------------------------------------------------------------
# Missed Call Handling
# ---------------------------------------------------------------------------


async def handle_missed_call(
    db: AsyncSession,
    from_number: str,
    to_number: str,
    settings: Settings,
) -> CallLog | None:
    """Handle a missed call: log it and optionally send auto-reply SMS.

    Finds the user assigned to the to_number and creates a call log.
    Currently sends a default auto-reply SMS to the caller.
    """
    # Find the phone number record and its assigned user
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == to_number)
    )
    phone_record = result.scalar_one_or_none()
    user_id = phone_record.assigned_user_id if phone_record else None

    # Match contact
    contact = await _find_contact_by_phone(db, from_number)
    contact_id = contact.id if contact else None

    # Log the missed call
    call = CallLog(
        id=uuid.uuid4(),
        user_id=user_id,
        contact_id=contact_id,
        direction="inbound",
        from_number=from_number,
        to_number=to_number,
        duration_seconds=0,
        status="missed",
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Log to contact timeline
    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.CALL_LOGGED,
            title="Missed call",
            description=f"Missed call from {from_number}",
            reference_type="call_log",
            reference_id=call.id,
            user_id=user_id,
        )

    # Send auto-reply SMS
    try:
        client = _get_twilio_client(settings)
        auto_reply = "Sorry we missed your call. We will get back to you shortly."
        client.messages.create(
            body=auto_reply,
            from_=to_number if phone_record else settings.twilio_from_number,
            to=from_number,
        )

        # Log the auto-reply SMS
        auto_sms = SmsMessage(
            id=uuid.uuid4(),
            user_id=user_id,
            contact_id=contact_id,
            direction="outbound",
            from_number=to_number if phone_record else settings.twilio_from_number,
            to_number=from_number,
            body=auto_reply,
            status="sent",
        )
        db.add(auto_sms)
        await db.commit()
    except Exception:
        # If Twilio is not configured or fails, just skip auto-reply
        pass

    return call


# ---------------------------------------------------------------------------
# Live Chat
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncSession, data: LiveChatSessionCreate
) -> LiveChatSession:
    """Create a new live chat session. Match or create contact from email."""
    contact_id = None
    if data.visitor_email:
        result = await db.execute(
            select(Contact).where(Contact.email == data.visitor_email)
        )
        contact = result.scalar_one_or_none()
        if contact:
            contact_id = contact.id

    session = LiveChatSession(
        id=uuid.uuid4(),
        contact_id=contact_id,
        visitor_name=data.visitor_name,
        visitor_email=data.visitor_email,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def send_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    data: LiveChatMessageCreate,
    user: User | None = None,
) -> LiveChatMessage:
    """Send a message in a live chat session."""
    # Verify session exists
    result = await db.execute(
        select(LiveChatSession).where(LiveChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("LiveChatSession", str(session_id))

    message = LiveChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        contact_id=session.contact_id if data.direction == "inbound" else None,
        direction=data.direction,
        message=data.message,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def list_sessions(
    db: AsyncSession,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[LiveChatSession], int]:
    query = select(LiveChatSession)
    if status:
        query = query.where(LiveChatSession.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        query.order_by(LiveChatSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_session_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[LiveChatMessage], int]:
    # Verify session exists
    result = await db.execute(
        select(LiveChatSession).where(LiveChatSession.id == session_id)
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("LiveChatSession", str(session_id))

    count_q = select(func.count()).where(LiveChatMessage.session_id == session_id)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(LiveChatMessage)
        .where(LiveChatMessage.session_id == session_id)
        .order_by(LiveChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def close_session(db: AsyncSession, session_id: uuid.UUID) -> LiveChatSession:
    result = await db.execute(
        select(LiveChatSession).where(LiveChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("LiveChatSession", str(session_id))
    session.status = "closed"
    await db.commit()
    await db.refresh(session)
    return session
