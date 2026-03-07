
import logging
import uuid
from typing import Optional

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError

from .models import MessageDirection, MessageType, UnifiedMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Record outbound messages
# ---------------------------------------------------------------------------


async def record_outbound_email(
    db: AsyncSession,
    user_id: uuid.UUID,
    to_email: str,
    subject: str,
    body_snippet: str,
    contact_id: Optional[uuid.UUID] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> UnifiedMessage:
    """Record an outbound email in the unified inbox.

    Thread ID is derived as ``email:{contact_id}`` when a contact is linked,
    otherwise ``email:{to_email}``.  Duplicate messages are detected via
    ``source_type`` + ``source_id`` when both are provided.
    """
    # Dedup check: skip if this source message was already recorded.
    if source_type and source_id:
        result = await db.execute(
            select(UnifiedMessage).where(
                UnifiedMessage.source_type == source_type,
                UnifiedMessage.source_id == source_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    thread_id = f"email:{contact_id}" if contact_id else f"email:{to_email}"
    msg = UnifiedMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        contact_id=contact_id,
        message_type=MessageType.EMAIL,
        direction=MessageDirection.OUTBOUND,
        subject=subject,
        body=body_snippet[:2000] if body_snippet else None,
        recipient=to_email,
        is_read=True,  # outbound messages are already "read"
        thread_id=thread_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(msg)
    await db.flush()
    return msg


async def record_outbound_sms(
    db: AsyncSession,
    user_id: uuid.UUID,
    to_phone: str,
    body: str,
    contact_id: Optional[uuid.UUID] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> UnifiedMessage:
    """Record an outbound SMS in the unified inbox.

    Thread ID is derived as ``sms:{contact_id}`` when a contact is linked,
    otherwise ``sms:{to_phone}``.  Duplicate messages are detected via
    ``source_type`` + ``source_id`` when both are provided.
    """
    # Dedup check
    if source_type and source_id:
        result = await db.execute(
            select(UnifiedMessage).where(
                UnifiedMessage.source_type == source_type,
                UnifiedMessage.source_id == source_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    thread_id = f"sms:{contact_id}" if contact_id else f"sms:{to_phone}"
    msg = UnifiedMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        contact_id=contact_id,
        message_type=MessageType.SMS,
        direction=MessageDirection.OUTBOUND,
        subject=None,
        body=body[:2000] if body else None,
        recipient=to_phone,
        is_read=True,  # outbound messages are already "read"
        thread_id=thread_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(msg)
    await db.flush()
    return msg


# ---------------------------------------------------------------------------
# Sync existing SMS logs (one-time backfill)
# ---------------------------------------------------------------------------


async def sync_existing_messages(db: AsyncSession, user_id: uuid.UUID) -> int:
    """One-time sync of existing SmsLog entries into the unified inbox.

    Idempotent: uses ``source_type='sms_log'`` + ``source_id=str(sms_log.id)``
    for dedup so the same log is never imported twice.
    """
    from app.integrations.twilio.models import SmsLog

    result = await db.execute(
        select(SmsLog).where(SmsLog.created_by == user_id)
    )
    sms_logs = result.scalars().all()

    created_count = 0
    for log in sms_logs:
        # Attempt to resolve a contact by phone number
        contact_id = await _resolve_contact_by_phone(db, user_id, log.recipient)

        msg = await record_outbound_sms(
            db,
            user_id=user_id,
            to_phone=log.recipient,
            body=log.message,
            contact_id=contact_id,
            source_type="sms_log",
            source_id=str(log.id),
        )
        # If the message was freshly created (not deduped), count it
        if msg.source_id == str(log.id):
            created_count += 1

    await db.commit()
    return created_count


async def _resolve_contact_by_phone(
    db: AsyncSession,
    user_id: uuid.UUID,
    phone: str,
) -> Optional[uuid.UUID]:
    """Try to find a contact by phone number for the given user."""
    from app.contacts.models import Contact

    result = await db.execute(
        select(Contact.id).where(
            Contact.created_by == user_id,
            Contact.phone == phone,
        )
    )
    row = result.scalar_one_or_none()
    return row if row else None


# ---------------------------------------------------------------------------
# Listing & querying
# ---------------------------------------------------------------------------


async def list_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    message_type: Optional[MessageType] = None,
    direction: Optional[MessageDirection] = None,
    contact_id: Optional[uuid.UUID] = None,
    is_read: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[UnifiedMessage], int]:
    """List messages with optional filters. Returns (messages, total_count)."""
    base = select(UnifiedMessage).where(UnifiedMessage.user_id == user_id)

    if message_type is not None:
        base = base.where(UnifiedMessage.message_type == message_type)
    if direction is not None:
        base = base.where(UnifiedMessage.direction == direction)
    if contact_id is not None:
        base = base.where(UnifiedMessage.contact_id == contact_id)
    if is_read is not None:
        base = base.where(UnifiedMessage.is_read == is_read)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            UnifiedMessage.subject.ilike(pattern)
            | UnifiedMessage.body.ilike(pattern)
            | UnifiedMessage.recipient.ilike(pattern)
            | UnifiedMessage.sender.ilike(pattern)
        )

    # Total count
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginated results
    query = base.order_by(UnifiedMessage.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    messages = list(result.scalars().all())

    return messages, total


async def list_threads(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Group messages by thread_id and return the latest message per thread.

    Returns a list of dicts containing ``message`` (the latest UnifiedMessage)
    and ``message_count`` (total messages in the thread), plus the total number
    of distinct threads.
    """
    # Subquery: latest created_at and count per thread
    thread_stats = (
        select(
            UnifiedMessage.thread_id,
            func.max(UnifiedMessage.created_at).label("latest_at"),
            func.count(UnifiedMessage.id).label("msg_count"),
            func.sum(
                case((UnifiedMessage.is_read.is_(False), 1), else_=0)
            ).label("unread_count"),
        )
        .where(
            UnifiedMessage.user_id == user_id,
            UnifiedMessage.thread_id.isnot(None),
        )
        .group_by(UnifiedMessage.thread_id)
        .subquery()
    )

    # Total distinct threads
    total_query = select(func.count()).select_from(thread_stats)
    total = (await db.execute(total_query)).scalar() or 0

    # Paginated thread stats ordered by latest message
    offset = (page - 1) * page_size
    paginated_stats = (
        select(thread_stats)
        .order_by(thread_stats.c.latest_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    stats_result = await db.execute(paginated_stats)
    stats_rows = stats_result.all()

    threads: list[dict] = []
    for row in stats_rows:
        # Fetch the actual latest message for this thread
        msg_result = await db.execute(
            select(UnifiedMessage)
            .where(
                UnifiedMessage.user_id == user_id,
                UnifiedMessage.thread_id == row.thread_id,
            )
            .order_by(UnifiedMessage.created_at.desc())
            .limit(1)
        )
        latest_msg = msg_result.scalar_one_or_none()
        if latest_msg:
            threads.append(
                {
                    "message": latest_msg,
                    "message_count": row.msg_count,
                    "unread_count": row.unread_count,
                }
            )

    return threads, total


async def get_thread_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    thread_id: str,
) -> list[UnifiedMessage]:
    """Get all messages in a thread, ordered by created_at ascending."""
    result = await db.execute(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.user_id == user_id,
            UnifiedMessage.thread_id == thread_id,
        )
        .order_by(UnifiedMessage.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Read status
# ---------------------------------------------------------------------------


async def mark_as_read(db: AsyncSession, message_id: uuid.UUID) -> None:
    """Mark a single message as read."""
    await db.execute(
        update(UnifiedMessage)
        .where(UnifiedMessage.id == message_id)
        .values(is_read=True)
    )
    await db.commit()


async def mark_thread_as_read(
    db: AsyncSession,
    thread_id: str,
    user_id: uuid.UUID,
) -> None:
    """Mark all messages in a thread as read."""
    await db.execute(
        update(UnifiedMessage)
        .where(
            UnifiedMessage.thread_id == thread_id,
            UnifiedMessage.user_id == user_id,
            UnifiedMessage.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Unread counts
# ---------------------------------------------------------------------------


async def get_unread_counts(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Return ``{total, email, sms}`` unread counts for the user."""
    result = await db.execute(
        select(
            UnifiedMessage.message_type,
            func.count(UnifiedMessage.id).label("cnt"),
        )
        .where(
            UnifiedMessage.user_id == user_id,
            UnifiedMessage.is_read.is_(False),
        )
        .group_by(UnifiedMessage.message_type)
    )
    rows = result.all()

    counts = {"total": 0, "email": 0, "sms": 0}
    for row in rows:
        if row.message_type == MessageType.EMAIL:
            counts["email"] = row.cnt
        elif row.message_type == MessageType.SMS:
            counts["sms"] = row.cnt
        counts["total"] += row.cnt

    return counts


# ---------------------------------------------------------------------------
# Reply (send + record)
# ---------------------------------------------------------------------------


async def send_reply(
    db: AsyncSession,
    user: User,
    thread_id: str,
    body: str,
    subject: Optional[str] = None,
    smtp_config_id: Optional[uuid.UUID] = None,
    settings: Optional[Settings] = None,
) -> UnifiedMessage:
    """Reply to a thread.

    Parses the ``thread_id`` prefix to determine the channel:
    - ``email:<identifier>``  -- sends via SMTP and records the outbound email.
    - ``sms:<identifier>``    -- sends via Twilio and records the outbound SMS.
    """
    if ":" not in thread_id:
        raise ValidationError(f"Invalid thread_id format: {thread_id}")

    channel, identifier = thread_id.split(":", 1)

    if channel == "email":
        return await _reply_email(
            db, user, thread_id, identifier, body, subject, smtp_config_id
        )
    elif channel == "sms":
        return await _reply_sms(db, user, thread_id, identifier, body, settings)
    else:
        raise ValidationError(f"Unsupported thread channel: {channel}")


async def _reply_email(
    db: AsyncSession,
    user: User,
    thread_id: str,
    identifier: str,
    body: str,
    subject: Optional[str],
    smtp_config_id: Optional[uuid.UUID],
) -> UnifiedMessage:
    """Send an email reply and record it in the unified inbox."""
    from app.email.service import resolve_smtp_config, send_email

    # Resolve SMTP configuration
    smtp_config = await resolve_smtp_config(db, user, smtp_config_id)

    # Determine recipient email: the identifier may be a UUID (contact) or email
    to_email: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None

    try:
        contact_uuid = uuid.UUID(identifier)
        # It is a contact UUID -- look up their email
        from app.contacts.models import Contact

        result = await db.execute(
            select(Contact).where(Contact.id == contact_uuid)
        )
        contact = result.scalar_one_or_none()
        if contact and contact.email:
            to_email = contact.email
            contact_id = contact.id
        else:
            raise ValidationError(
                "Contact has no email address on file."
            )
    except ValueError:
        # Not a UUID -- treat as raw email address
        to_email = identifier

    if not to_email:
        raise ValidationError("Unable to determine recipient email for reply.")

    email_subject = subject or "Re: (no subject)"

    # Build a simple HTML body for the reply
    html_body = f"<p>{body}</p>"

    await send_email(smtp_config, to_email, email_subject, html_body)

    # Record in unified inbox
    msg = await record_outbound_email(
        db,
        user_id=user.id,
        to_email=to_email,
        subject=email_subject,
        body_snippet=body,
        contact_id=contact_id,
        source_type="inbox_reply",
        source_id=str(uuid.uuid4()),
    )
    await db.commit()
    return msg


async def _reply_sms(
    db: AsyncSession,
    user: User,
    thread_id: str,
    identifier: str,
    body: str,
    settings: Optional[Settings],
) -> UnifiedMessage:
    """Send an SMS reply via Twilio and record it in the unified inbox."""
    from app.integrations.twilio.service import send_sms

    if settings is None:
        from app.config import Settings as SettingsClass

        settings = SettingsClass()

    # Determine recipient phone: identifier may be a UUID (contact) or phone
    to_phone: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None

    try:
        contact_uuid = uuid.UUID(identifier)
        from app.contacts.models import Contact

        result = await db.execute(
            select(Contact).where(Contact.id == contact_uuid)
        )
        contact = result.scalar_one_or_none()
        if contact and contact.phone:
            to_phone = contact.phone
            contact_id = contact.id
        else:
            raise ValidationError(
                "Contact has no phone number on file."
            )
    except ValueError:
        # Not a UUID -- treat as raw phone number
        to_phone = identifier

    if not to_phone:
        raise ValidationError("Unable to determine recipient phone for reply.")

    # Send via Twilio (this also creates an SmsLog entry)
    sms_log = await send_sms(db, to_phone, body, user, settings)

    # Record in unified inbox
    msg = await record_outbound_sms(
        db,
        user_id=user.id,
        to_phone=to_phone,
        body=body,
        contact_id=contact_id,
        source_type="sms_log",
        source_id=str(sms_log.id),
    )
    await db.commit()
    return msg
