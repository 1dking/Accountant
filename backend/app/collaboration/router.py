
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.collaboration.schemas import (
    ActivityFilter,
    ActivityLogResponse,
    ApprovalRequest,
    ApprovalResolve,
    ApprovalResponse,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
)
from app.collaboration.service import (
    cancel_approval,
    create_comment,
    delete_comment,
    list_activity,
    list_comments,
    list_pending_approvals,
    request_approval,
    resolve_approval,
    update_comment,
)
from app.core.pagination import PaginationParams, build_pagination_meta, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ── Comments ──────────────────────────────────────────────────────────────────


@router.get("/documents/{document_id}/comments")
async def get_document_comments(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    comments = await list_comments(db, document_id)
    return {"data": [CommentResponse.model_validate(c) for c in comments]}


@router.post("/documents/{document_id}/comments", status_code=201)
async def add_comment(
    document_id: uuid.UUID,
    body: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    comment = await create_comment(
        db,
        document_id=document_id,
        user_id=current_user.id,
        content=body.content,
        parent_id=body.parent_id,
    )
    return {"data": CommentResponse.model_validate(comment)}


@router.put("/comments/{comment_id}")
async def edit_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    comment = await update_comment(
        db,
        comment_id=comment_id,
        user_id=current_user.id,
        content=body.content,
    )
    return {"data": CommentResponse.model_validate(comment)}


@router.delete("/comments/{comment_id}")
async def remove_comment(
    comment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    is_admin = current_user.role == Role.ADMIN
    await delete_comment(
        db,
        comment_id=comment_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    return {"data": {"message": "Comment deleted"}}


# ── Activity feed ─────────────────────────────────────────────────────────────


@router.get("/activity")
async def get_activity_feed(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> dict:
    filters = ActivityFilter(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    entries, total_count = await list_activity(db, filters, pagination)
    return {
        "data": [ActivityLogResponse.model_validate(e) for e in entries],
        "meta": build_pagination_meta(total_count, pagination),
    }


# ── Approvals ─────────────────────────────────────────────────────────────────


@router.post("/documents/{document_id}/approve", status_code=201)
async def create_approval_request(
    document_id: uuid.UUID,
    body: ApprovalRequest,
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    approval = await request_approval(
        db,
        document_id=document_id,
        requested_by=current_user.id,
        assigned_to=body.assigned_to,
    )
    return {"data": ApprovalResponse.model_validate(approval)}


@router.put("/approvals/{approval_id}")
async def resolve_approval_endpoint(
    approval_id: uuid.UUID,
    body: ApprovalResolve,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    is_admin = current_user.role == Role.ADMIN
    approval = await resolve_approval(
        db,
        approval_id=approval_id,
        resolver_id=current_user.id,
        status=body.status,
        comment=body.comment,
        is_admin=is_admin,
    )
    return {"data": ApprovalResponse.model_validate(approval)}


@router.get("/approvals")
async def get_pending_approvals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    approvals, total_count = await list_pending_approvals(
        db, current_user.id, pagination
    )
    return {
        "data": [ApprovalResponse.model_validate(a) for a in approvals],
        "meta": build_pagination_meta(total_count, pagination),
    }


@router.delete("/approvals/{approval_id}")
async def cancel_approval_endpoint(
    approval_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    is_admin = current_user.role == Role.ADMIN
    approval = await cancel_approval(
        db,
        approval_id=approval_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    return {"data": ApprovalResponse.model_validate(approval)}
