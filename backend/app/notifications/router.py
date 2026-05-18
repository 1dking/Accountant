
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
    get_unread_count,
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


@router.get("/preferences")
async def get_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return the user's notification preference matrix.

    For every known notification_type (in NOTIFICATION_TYPE_LABELS),
    return either the user's saved row OR the DEFAULT_PREFERENCES entry.
    Single endpoint = full matrix in one round-trip.
    """
    from sqlalchemy import select
    from app.notifications.models import NotificationPreference
    from app.notifications.service import (
        DEFAULT_PREFERENCES,
        NOTIFICATION_TYPE_LABELS,
    )

    rows = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    by_type = {p.notification_type: p for p in rows.scalars().all()}

    items = []
    for type_key, label in NOTIFICATION_TYPE_LABELS.items():
        pref = by_type.get(type_key)
        if pref is not None:
            items.append({
                "type": type_key,
                "label": label,
                "in_app": pref.in_app,
                "email": pref.email,
                "sms": pref.sms,
            })
        else:
            d = DEFAULT_PREFERENCES.get(type_key) or DEFAULT_PREFERENCES["_default"]
            items.append({
                "type": type_key,
                "label": label,
                "in_app": d["in_app"],
                "email": d["email"],
                "sms": d["sms"],
            })

    return {
        "data": {
            "items": items,
            "fallback_phone": current_user.fallback_phone,
        }
    }


@router.put("/preferences")
async def update_notification_preferences(
    body: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Upsert preferences. Body: { items: [{ type, in_app, email, sms }] }."""
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.notifications.models import NotificationPreference
    from app.notifications.service import NOTIFICATION_TYPE_LABELS

    items = body.get("items")
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="'items' must be a list")

    known = set(NOTIFICATION_TYPE_LABELS.keys())
    existing_rows = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    existing_by_type = {p.notification_type: p for p in existing_rows.scalars().all()}

    updated = 0
    for item in items:
        t = item.get("type")
        if t not in known:
            raise HTTPException(
                status_code=400, detail=f"Unknown notification_type: {t}"
            )
        in_app = bool(item.get("in_app", True))
        email_v = bool(item.get("email", False))
        sms_v = bool(item.get("sms", False))

        pref = existing_by_type.get(t)
        if pref is not None:
            pref.in_app = in_app
            pref.email = email_v
            pref.sms = sms_v
        else:
            import uuid as _uuid
            db.add(NotificationPreference(
                id=_uuid.uuid4(),
                user_id=current_user.id,
                notification_type=t,
                in_app=in_app,
                email=email_v,
                sms=sms_v,
            ))
        updated += 1

    await db.commit()
    return {"data": {"updated": updated}}


@router.get("/unread-count")
async def get_notifications_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Lightweight endpoint for bell-badge polling. Returns { count: N }."""
    count = await get_unread_count(db, current_user.id)
    return {"data": {"count": count}}


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
