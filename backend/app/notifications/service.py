from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.core.websocket import websocket_manager
from app.notifications.models import Notification


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
