"""Data-rights endpoints: self-service export + deletion, and admin-operated
export/deletion for verified access/erasure requests."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.privacy import service
from app.privacy.schemas import DeleteRequest

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Self-service
# ---------------------------------------------------------------------------


@router.post("/me/export")
async def export_my_data(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    data = await service.export_user_data(db, current_user)
    await safe_record_audit(
        db,
        action=AuditAction.DATA_EXPORTED,
        result=AuditResult.SUCCESS,
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="user",
        resource_id=str(current_user.id),
        ip_address=_client_ip(request),
        metadata={"scope": "self"},
    )
    return {"data": data}


@router.post("/me/delete")
async def delete_my_data(
    body: DeleteRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if body.confirm != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation required: send {"confirm": "DELETE"} to erase your data.',
        )
    summary = await service.delete_user_data(
        db, current_user, actor=current_user, reason=body.reason, ip=_client_ip(request)
    )
    return {"data": {"deleted": True, "summary": summary}}


# ---------------------------------------------------------------------------
# Admin-operated (verified request handling)
# ---------------------------------------------------------------------------


async def _load_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/admin/users/{user_id}/export")
async def admin_export_user(
    user_id: uuid.UUID,
    request: Request,
    admin: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    target = await _load_user(db, user_id)
    data = await service.export_user_data(db, target)
    await safe_record_audit(
        db,
        action=AuditAction.DATA_EXPORTED,
        result=AuditResult.SUCCESS,
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="user",
        resource_id=str(target.id),
        ip_address=_client_ip(request),
        metadata={"scope": "admin"},
    )
    return {"data": data}


@router.post("/admin/users/{user_id}/delete")
async def admin_delete_user(
    user_id: uuid.UUID,
    body: DeleteRequest,
    request: Request,
    admin: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if body.confirm != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation required: send {"confirm": "DELETE"}.',
        )
    target = await _load_user(db, user_id)
    summary = await service.delete_user_data(
        db, target, actor=admin, reason=body.reason, ip=_client_ip(request)
    )
    return {"data": {"deleted": True, "user_id": str(target.id), "summary": summary}}
