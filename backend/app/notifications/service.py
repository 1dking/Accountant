
import json
import logging
import uuid

from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.core.websocket import websocket_manager
from app.notifications.models import (
    Notification,
    NotificationPreference,
    PushSubscription,
)


# Default delivery preferences when no per-user row exists for a given
# notification_type. in_app=True everywhere — that's the cheap channel
# and the bell is the canonical surface. sms=True for high-urgency
# types where a buzz is worth interrupting your day.
DEFAULT_PREFERENCES = {
    "sms_inbound": {"in_app": True, "email": False, "sms": False},
    "voicemail_received": {"in_app": True, "email": False, "sms": True},
    "ai_reply_sent": {"in_app": True, "email": False, "sms": False},
    "automation_flow_completed": {"in_app": True, "email": False, "sms": False},
    "admin_reminder": {"in_app": True, "email": False, "sms": False},
    "identity_capture_asked": {"in_app": True, "email": False, "sms": False},
    "contact_auto_created": {"in_app": True, "email": False, "sms": False},
    "identity_capture_failed": {"in_app": True, "email": False, "sms": True},
    # Security event — your account just had its password changed. Email
    # is on by default so the trail goes to the address you used to
    # request the reset; SMS too because if it WASN'T you, you want to
    # know fast. (Effective once SMTP integration is wired up.)
    "password_changed": {"in_app": True, "email": True, "sms": True},
    # Fallback for any new type added later
    "_default": {"in_app": True, "email": False, "sms": False},
}


# Human-readable labels for the Settings UI. New types should add a
# row here AND a row in DEFAULT_PREFERENCES.
NOTIFICATION_TYPE_LABELS = {
    "sms_inbound": "New SMS message",
    "voicemail_received": "New voicemail",
    "ai_reply_sent": "AI replied on your behalf",
    "automation_flow_completed": "Automation completed",
    "admin_reminder": "Admin reminder",
    "identity_capture_asked": "Asked unknown caller for identity",
    "contact_auto_created": "Contact auto-created from SMS",
    "identity_capture_failed": "Couldn't capture identity",
    "password_changed": "Password changed",
}


async def _get_preferences(
    db: AsyncSession, user_id: uuid.UUID, notification_type: str
) -> dict:
    """Resolve effective preferences for (user, type). DB row wins over
    DEFAULT_PREFERENCES; default-of-defaults is in_app=True only."""
    row = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
    )
    pref = row.scalar_one_or_none()
    if pref is not None:
        return {"in_app": pref.in_app, "email": pref.email, "sms": pref.sms}
    return DEFAULT_PREFERENCES.get(notification_type) or DEFAULT_PREFERENCES["_default"]

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    link_path: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> Notification | None:
    """Create a notification record (gated by user preferences) + dispatch
    via WS, email-log, and SMS-to-cell per preference matrix.

    Returns the Notification row if in_app=True, else None (other channels
    still fired). All side-channel failures are isolated — they never
    block the in-app row creation.
    """
    prefs = await _get_preferences(db, user_id, type)

    notification: Notification | None = None
    if prefs.get("in_app", True):
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            link_path=link_path,
            contact_id=contact_id,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
    else:
        logger.info(
            "notifications.gated_out_in_app user_id=%s type=%s "
            "(user disabled the in-app channel for this type)",
            user_id, type,
        )

    # Email channel — dispatch via the user's SMTP config (falling back
    # to system default). Failure NEVER blocks the in-app row: SMTP can
    # be unconfigured during local dev, the mailbox can be unreachable,
    # the user might not have a valid email — none of those should kill
    # the notification entirely. We log and move on.
    if prefs.get("email", False):
        try:
            await _send_email_notification(
                db,
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                link_path=link_path,
            )
        except Exception as e:
            logger.warning(
                "notifications.email_channel_failed user_id=%s type=%s error=%s",
                user_id, type, str(e)[:200],
            )

    # SMS-to-cell channel — sends to user.fallback_phone via Twilio.
    # Wrapped in try/except so an SMS failure can't break the in-app
    # row or the parent feature. Never creates a notification for the
    # outbound SMS itself (no recursion).
    if prefs.get("sms", False):
        try:
            await _send_sms_notification(db, user_id, title, message)
        except Exception as e:
            logger.warning(
                "notifications.sms_channel_failed user_id=%s type=%s error=%s",
                user_id, type, str(e)[:200],
            )

    # Push real-time event via WebSocket. The frontend wsClient dispatches
    # on the "type" field, so use that consistently. Only fire when the
    # in-app row exists — no point pushing a phantom event.
    if notification is not None:
        await websocket_manager.send_to_user(
            str(user_id),
            {
                "type": "notification",
                "data": {
                    "id": str(notification.id),
                    "user_id": str(user_id),
                    "type": type,
                    "title": title,
                    "message": message,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "link_path": link_path,
                    "contact_id": str(contact_id) if contact_id else None,
                    "is_read": False,
                    "created_at": notification.created_at.isoformat()
                    if notification.created_at else None,
                },
            },
        )

    return notification


async def _send_email_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    link_path: str | None,
) -> None:
    """Render notification.html and dispatch via the user's SMTP config.

    If the user has no resolvable SMTP config (and no system default
    exists), we log and bail — better to skip than to surface an SMTP
    error to the caller. This is the channel where "user wants email
    but the platform isn't fully wired" needs to fail gracefully.
    """
    from datetime import datetime, timezone

    from app.auth.models import User
    from app.config import Settings
    from app.email.service import render_template, resolve_smtp_config, send_email

    row = await db.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None or not user.email:
        logger.info(
            "notifications.email_channel_skipped_no_user user_id=%s", user_id
        )
        return

    try:
        smtp_config = await resolve_smtp_config(db, user, None)
    except NotFoundError:
        logger.info(
            "notifications.email_channel_skipped_no_smtp user_id=%s type=%s "
            "— no user or system SMTP config configured",
            user_id, type,
        )
        return

    settings = Settings()
    base_url = settings.public_base_url.rstrip("/")
    link_url = f"{base_url}{link_path}" if link_path else None
    preferences_url = f"{base_url}/settings?tab=notif-prefs"
    type_label = NOTIFICATION_TYPE_LABELS.get(type, type.replace("_", " ").title())

    html_body = render_template(
        "notification.html",
        title=title,
        message=message,
        link_url=link_url,
        link_label="Open in app",
        type_label=type_label,
        type=type,
        preferences_url=preferences_url,
        company_name=smtp_config.from_name,
        year=datetime.now(timezone.utc).year,
    )

    await send_email(
        smtp_config,
        to=user.email,
        subject=f"[{smtp_config.from_name}] {title}",
        html_body=html_body,
    )
    logger.info(
        "notifications.email_channel_sent user_id=%s to=%s type=%s",
        user_id, user.email, type,
    )


async def _send_sms_notification(
    db: AsyncSession, user_id: uuid.UUID, title: str, message: str
) -> None:
    """Send a notification SMS to the user's fallback_phone.

    Uses Twilio's Python SDK directly (not communication.service.send_sms)
    so we don't loop — send_sms calls invalidate_brief_cache, persists an
    SmsMessage row, etc. We just want a raw SMS to the user's cell.
    """
    from app.auth.models import User
    from app.config import Settings

    settings = Settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.info(
            "notifications.sms_channel_skipped_no_twilio user_id=%s", user_id
        )
        return

    row = await db.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None or not user.fallback_phone:
        logger.info(
            "notifications.sms_channel_skipped_no_fallback user_id=%s", user_id
        )
        return

    body = f"[{title}] {message}"[:1500]
    from_number = settings.twilio_from_number or None
    if not from_number:
        # Try the user's assigned Twilio number as the FROM
        from app.communication.models import TwilioPhoneNumber

        phone_row = await db.execute(
            select(TwilioPhoneNumber).where(
                TwilioPhoneNumber.assigned_user_id == user_id
            )
        )
        phone = phone_row.scalar_one_or_none()
        from_number = phone.phone_number if phone else None
    if not from_number:
        logger.warning(
            "notifications.sms_channel_skipped_no_from_number user_id=%s",
            user_id,
        )
        return

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(body=body, from_=from_number, to=user.fallback_phone)
    logger.info(
        "notifications.sms_channel_sent user_id=%s to=%s chars=%d",
        user_id, user.fallback_phone, len(body),
    )


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Lightweight count-only endpoint for bell-badge polling."""
    return await db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    ) or 0


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    pagination: PaginationParams,
) -> tuple[list[Notification], int, int]:
    """Return paginated notifications for a user, plus total count and unread count."""
    # Total count
    total_count = await db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id
        )
    ) or 0

    # Unread count
    unread_count = await db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    ) or 0

    # Paginated results
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    notifications = list(result.scalars().all())

    return notifications, total_count, unread_count


async def mark_read(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification:
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification", str(notification_id))

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_read(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Mark all notifications as read for a user. Returns the number updated."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount  # type: ignore[return-value]


async def delete_notification(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a single notification owned by the user."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification", str(notification_id))

    await db.delete(notification)
    await db.commit()


# ---------------------------------------------------------------------------
# Push Subscriptions
# ---------------------------------------------------------------------------


async def save_push_subscription(
    db: AsyncSession,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
) -> PushSubscription:
    """Save or update a push subscription for a user."""
    # Check if this endpoint already exists
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.user_id = user_id
        existing.p256dh_key = p256dh_key
        existing.auth_key = auth_key
        await db.commit()
        await db.refresh(existing)
        return existing

    sub = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh_key=p256dh_key,
        auth_key=auth_key,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def remove_push_subscription(
    db: AsyncSession,
    user_id: uuid.UUID,
    endpoint: str,
) -> None:
    """Remove a push subscription."""
    await db.execute(
        sa_delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    await db.commit()


async def send_push_to_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    url: str | None = None,
    settings=None,
) -> int:
    """Send web push notification to all subscriptions for a user.

    Returns the number of successfully sent notifications.
    """
    if not settings or not settings.vapid_private_key:
        return 0

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subscriptions = result.scalars().all()

    if not subscriptions:
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.debug("pywebpush not installed, skipping push notifications")
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/",
        "icon": "/icons/icon-192x192.png",
    })

    sent = 0
    stale_endpoints = []

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_email},
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                stale_endpoints.append(sub.endpoint)
            else:
                logger.warning("Push notification failed: %s", e)
        except Exception as e:
            logger.warning("Push notification error: %s", e)

    # Clean up stale subscriptions
    for endpoint in stale_endpoints:
        await db.execute(
            sa_delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )

    if stale_endpoints:
        await db.commit()

    return sent
