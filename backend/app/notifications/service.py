
import json
import logging
import uuid

from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.core.websocket import websocket_manager
from app.notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    """Create a notification record and push it via WebSocket."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Push real-time event via WebSocket
    await websocket_manager.send_to_user(
        str(user_id),
        {
            "event": "notification",
            "data": {
                "id": str(notification.id),
                "type": type,
                "title": title,
                "message": message,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        },
    )

    return notification


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
