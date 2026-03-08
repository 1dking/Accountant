
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.pagination import PaginationParams, build_pagination_meta, get_pagination
from app.dependencies import get_current_user, get_db
from app.notifications.schemas import NotificationResponse
from app.notifications.service import (
    delete_notification,
    list_notifications,
    mark_all_read,
    mark_read,
    remove_push_subscription,
    save_push_subscription,
)

router = APIRouter()


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("")
async def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    notifications, total_count, unread_count = await list_notifications(
        db, current_user.id, pagination
    )
    meta = build_pagination_meta(total_count, pagination)
    meta["unread_count"] = unread_count
    return {
        "data": [NotificationResponse.model_validate(n) for n in notifications],
        "meta": meta,
    }


@router.put("/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    notification = await mark_read(db, notification_id, current_user.id)
    return {"data": NotificationResponse.model_validate(notification)}


@router.put("/read-all")
async def read_all_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    count = await mark_all_read(db, current_user.id)
    return {"data": {"message": f"Marked {count} notifications as read"}}


@router.delete("/{notification_id}")
async def remove_notification(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await delete_notification(db, notification_id, current_user.id)
    return {"data": {"message": "Notification deleted"}}


# ---------------------------------------------------------------------------
# Push Subscriptions
# ---------------------------------------------------------------------------


@router.get("/push/vapid-key")
async def get_vapid_public_key(request: Request) -> dict:
    """Return the VAPID public key for the frontend to subscribe."""
    settings = request.app.state.settings
    return {"data": {"public_key": settings.vapid_public_key}}


@router.post("/push/subscribe")
async def subscribe_push(
    data: PushSubscribeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    sub = await save_push_subscription(
        db, current_user.id, data.endpoint, data.p256dh, data.auth
    )
    return {"data": {"id": str(sub.id), "message": "Subscribed to push notifications"}}


@router.post("/push/unsubscribe")
async def unsubscribe_push(
    data: PushUnsubscribeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await remove_push_subscription(db, current_user.id, data.endpoint)
    return {"data": {"message": "Unsubscribed from push notifications"}}
