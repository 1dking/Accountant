
import math
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.inbox import service
from app.inbox.models import MessageDirection, MessageType
from app.inbox.schemas import SendReplyRequest, UnifiedMessageResponse, UnreadCount

router = APIRouter()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@router.get("/messages")
async def list_messages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    message_type: Optional[MessageType] = Query(None),
    direction: Optional[MessageDirection] = Query(None),
    contact_id: Optional[uuid.UUID] = Query(None),
    is_read: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    messages, total = await service.list_messages(
        db,
        user_id=current_user.id,
        message_type=message_type,
        direction=direction,
        contact_id=contact_id,
        is_read=is_read,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [UnifiedMessageResponse.model_validate(m) for m in messages],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------


@router.get("/threads")
async def list_threads(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    threads, total = await service.list_threads(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [
            {
                "message": UnifiedMessageResponse.model_validate(t["message"]),
                "message_count": t["message_count"],
                "unread_count": t["unread_count"],
            }
            for t in threads
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.get("/threads/{thread_id}")
async def get_thread_messages(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    messages = await service.get_thread_messages(db, current_user.id, thread_id)
    return {
        "data": [UnifiedMessageResponse.model_validate(m) for m in messages],
        "meta": {"count": len(messages)},
    }


@router.post("/threads/{thread_id}/reply", status_code=201)
async def reply_to_thread(
    thread_id: str,
    data: SendReplyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    settings = request.app.state.settings
    msg = await service.send_reply(
        db,
        user=current_user,
        thread_id=thread_id,
        body=data.body,
        subject=data.subject,
        smtp_config_id=data.smtp_config_id,
        settings=settings,
    )
    return {"data": UnifiedMessageResponse.model_validate(msg)}


# ---------------------------------------------------------------------------
# Read status
# ---------------------------------------------------------------------------


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    await service.mark_as_read(db, message_id)
    return {"data": {"message": "Message marked as read"}}


@router.post("/threads/{thread_id}/read")
async def mark_thread_read(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    await service.mark_thread_as_read(db, thread_id, current_user.id)
    return {"data": {"message": "Thread marked as read"}}


# ---------------------------------------------------------------------------
# Unread counts
# ---------------------------------------------------------------------------


@router.get("/unread-count")
async def unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    counts = await service.get_unread_counts(db, current_user.id)
    return {"data": UnreadCount(**counts)}


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


@router.post("/sync")
async def sync_messages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    created = await service.sync_existing_messages(db, current_user.id)
    return {
        "data": {
            "message": f"Synced {created} new message(s) into unified inbox",
            "created": created,
        }
    }
