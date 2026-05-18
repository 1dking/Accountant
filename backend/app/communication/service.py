
import json
import logging
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

logger = logging.getLogger(__name__)


def _strip_non_digits(phone: str) -> str:
    """Strip all non-digit characters for phone-number comparison.

    NANP normalization: drop a leading 1 from 11-digit results so
    '+12896984168' compares equal to '2896984168'.

    WARNING: This is North American (NANP) specific. International
    numbers (UK +44, AU +61, etc.) won't normalize correctly with
    this rule. When/if Accountant goes international, switch to a
    proper E.164 parser like the phonenumbers library.
    """
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


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
            logger.info(
                "contact_match.resolved phone=%s contact_id=%s",
                phone, contact.id,
            )
            return contact
    logger.info("contact_match.not_found phone=%s normalized=%s", phone, stripped)
    return None


def _get_twilio_client(settings: Settings):
    from twilio.rest import Client

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValidationError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


# Webhook path constants — kept in lockstep with the @router decorators in
# router.py. If you rename a route there, update here too. These are
# CONCATENATED with settings.public_base_url + the /api/communication prefix
# (set in main.py) to produce the absolute URLs Twilio posts to.
WEBHOOK_PATH_VOICE_INCOMING = "/voice/incoming"
WEBHOOK_PATH_VOICE_FALLBACK = "/voice/incoming-fallback"
WEBHOOK_PATH_SMS = "/sms/webhook"
WEBHOOK_PATH_CALL_STATUS = "/voice/call-status"


def build_webhook_urls(settings: Settings) -> dict[str, str]:
    """Return absolute URLs for the webhooks Twilio needs to call on our
    behalf for each phone number. Driven by settings.public_base_url so the
    config follows the deployment environment.

    Returned dict keys match the kwargs Twilio's IncomingPhoneNumber.update
    accepts: voice_url, voice_fallback_url, sms_url, status_callback.
    """
    base = (settings.public_base_url or "").rstrip("/")
    api_prefix = f"{base}/api/communication"
    return {
        "voice_url": f"{api_prefix}{WEBHOOK_PATH_VOICE_INCOMING}",
        "voice_fallback_url": f"{api_prefix}{WEBHOOK_PATH_VOICE_FALLBACK}",
        "sms_url": f"{api_prefix}{WEBHOOK_PATH_SMS}",
        "status_callback": f"{api_prefix}{WEBHOOK_PATH_CALL_STATUS}",
    }


async def configure_twilio_webhooks(
    settings: Settings, twilio_sid: str
) -> dict[str, str]:
    """Push our webhook URLs onto an existing Twilio IncomingPhoneNumber.

    Returns the urls dict on success. Raises ValueError on failure — caller
    decides whether to swallow (purchase flow keeps the number even if
    webhook config fails) or surface (sync endpoint).
    """
    urls = build_webhook_urls(settings)
    client = _get_twilio_client(settings)
    try:
        client.incoming_phone_numbers(twilio_sid).update(
            voice_url=urls["voice_url"],
            voice_method="POST",
            voice_fallback_url=urls["voice_fallback_url"],
            voice_fallback_method="POST",
            sms_url=urls["sms_url"],
            sms_method="POST",
            status_callback=urls["status_callback"],
            status_callback_method="POST",
        )
    except Exception as e:
        logger.error(
            "twilio_webhooks.configure_failed sid=%s error=%s",
            twilio_sid, str(e)[:200],
        )
        raise ValueError(f"Twilio webhook configuration failed: {str(e)[:200]}")
    logger.info("twilio_webhooks.configured sid=%s", twilio_sid)
    return urls


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


async def delete_phone_number(
    db: AsyncSession,
    phone_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.id == phone_id)
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        raise NotFoundError("TwilioPhoneNumber", str(phone_id))

    # Release at Twilio first (if we have a sid + working creds).
    # Order matters: Twilio release → DB delete. If Twilio fails,
    # abort and keep the DB row to avoid losing track of a still-billing number.
    twilio_sid: str | None = None
    if phone.capabilities_json:
        try:
            sid = json.loads(phone.capabilities_json).get("sid")
            if isinstance(sid, str) and sid.startswith("PN"):
                twilio_sid = sid
        except (json.JSONDecodeError, AttributeError):
            pass

    if twilio_sid:
        if settings and settings.twilio_account_sid and settings.twilio_auth_token:
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            try:
                client.incoming_phone_numbers(twilio_sid).delete()
            except Exception as e:
                raise ValidationError(f"Failed to release at Twilio: {str(e)[:200]}")
        else:
            logger.warning(
                "Deleting phone %s (sid=%s) without Twilio release — credentials missing. "
                "Number may continue billing.",
                phone_id, twilio_sid,
            )

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


async def get_capability_token(db: AsyncSession, user: User, settings: Settings) -> dict:
    """Generate a Twilio AccessToken with VoiceGrant for browser-based calling.

    Returns {"token": "...", "identity": "<user_uuid>"}. The identity is needed
    on the frontend to know which Twilio Client identity inbound calls will
    address (so we can match an incoming notification to "this is me").
    """
    missing = []
    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_api_key_sid:
        missing.append("TWILIO_API_KEY_SID")
    if not settings.twilio_api_key_secret:
        missing.append("TWILIO_API_KEY_SECRET")
    if not settings.twilio_twiml_app_sid:
        missing.append("TWILIO_TWIML_APP_SID")
    if missing:
        raise ValidationError(
            "Twilio Voice is not configured. Missing: " + ", ".join(missing)
        )

    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    identity = str(user.id)
    token = AccessToken(
        settings.twilio_account_sid,
        settings.twilio_api_key_sid,
        settings.twilio_api_key_secret,
        identity=identity,
        ttl=3600,
    )
    grant = VoiceGrant(
        outgoing_application_sid=settings.twilio_twiml_app_sid,
        incoming_allow=True,  # required so this identity can receive Twilio Client calls
    )
    token.add_grant(grant)
    return {"token": token.to_jwt(), "identity": identity}


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------


async def send_sms(
    db: AsyncSession, user: User, to_number: str, body: str, settings: Settings
) -> SmsMessage:
    """Send an SMS via Twilio and log it."""
    client = _get_twilio_client(settings)

    # Determine FROM: prefer the user's assigned Twilio number; fall back to the global.
    user_phone_result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.assigned_user_id == user.id)
    )
    user_phone = user_phone_result.scalar_one_or_none()
    from_number = user_phone.phone_number if user_phone else settings.twilio_from_number

    if not from_number:
        logger.warning(
            "send_sms: no FROM available for user %s — no assigned number and "
            "global twilio_from_number is empty. SMS send will fail.",
            user.id,
        )
        raise ValidationError(
            "No Twilio phone number available. Ask an admin to assign a number to your "
            "user, or set TWILIO_FROM_NUMBER as a global fallback."
        )

    # Try to match contact by phone number
    contact = await _find_contact_by_phone(db, to_number)
    contact_id = contact.id if contact else None

    try:
        twilio_message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number,
        )
        status = "sent"
        sid = twilio_message.sid
    except Exception:
        status = "failed"
        sid = None

    # Invalidate brief cache on the contact, fire-and-forget at commit
    if contact_id is not None:
        try:
            from app.contacts.ai_brief import invalidate_brief_cache
            await invalidate_brief_cache(db, contact_id)
        except Exception:
            pass
        # Manual user-initiated SMS → pause conversation engine for this
        # contact (user is talking, AI steps back). Safe no-op when not
        # otherwise active.
        try:
            from app.communication.conversation_engine import pause_for_manual_reply
            await pause_for_manual_reply(db, contact_id)
        except Exception:
            pass

    sms = SmsMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact_id,
        direction="outbound",
        from_number=from_number,
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

    # Resolve the owning user via the Twilio number that was dialed.
    # This is what the conversation engine + auto-reply features need to
    # identify "whose conversation is this".
    phone_row = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == to_number)
    )
    phone = phone_row.scalar_one_or_none()
    owner_user_id = phone.assigned_user_id if phone else None

    sms = SmsMessage(
        id=uuid.uuid4(),
        user_id=owner_user_id,
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

    # WebSocket fan-out for live Messages tab / Communication tab. The
    # Messages-tab thread filters by contact_id on the receiving end.
    # Wrapped in try/except — WS failure must NOT break inbound SMS.
    if owner_user_id is not None:
        try:
            from app.core.websocket import websocket_manager
            await websocket_manager.send_to_user(
                str(owner_user_id),
                {
                    "type": "sms.received",
                    "data": {
                        "sms_id": str(sms.id),
                        "contact_id": str(contact_id) if contact_id else None,
                        "from_number": from_number,
                        "body": (body or "")[:300],
                        "created_at": sms.created_at.isoformat() if sms.created_at else None,
                    },
                },
            )
        except Exception as e:
            logger.warning("ws.sms_received_publish_failed error=%s", str(e)[:200])

    # In-app notification for the user who owns this Twilio number.
    # Wrapped in try/except — notification failure must NOT break the
    # underlying inbound SMS flow.
    if owner_user_id is not None:
        try:
            from app.notifications.service import create_notification
            sender_label = (
                contact.contact_name or contact.company_name
                if contact else from_number
            )
            link_path = (
                f"/contacts/{contact_id}?tab=messages"
                if contact_id else "/communication?tab=sms"
            )
            await create_notification(
                db,
                user_id=owner_user_id,
                type="sms_inbound",
                title=f"New message from {sender_label}",
                message=(body or "")[:300],
                resource_type="sms_message",
                resource_id=str(sms.id),
                link_path=link_path,
                contact_id=contact_id,
            )
        except Exception as e:
            logger.warning(
                "notify.sms_inbound_failed sms_id=%s error=%s",
                sms.id, str(e)[:200],
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
