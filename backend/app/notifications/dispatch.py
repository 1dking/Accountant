
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import websocket_manager
from app.notifications.models import Notification


async def notify_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    """Create a notification for a specific user and push it via WebSocket."""
    notification = Notification(
        id=uuid.uuid4(),
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

    # Push via WebSocket
    await websocket_manager.send_to_user(
        str(user_id),
        {
            "type": "notification",
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


async def notify_admins(
    db: AsyncSession,
    type: str,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> list[Notification]:
    """Create notifications for all active admin users and push via WebSocket."""
    from app.auth.models import Role, User

    result = await db.execute(
        select(User).where(
            User.role == Role.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    notifications = []
    for user in result.scalars().all():
        notification = await notify_user(
            db,
            user_id=user.id,
            type=type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        notifications.append(notification)
    return notifications
