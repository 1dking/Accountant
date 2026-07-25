"""Platform-admin query surface for the audit log (read-only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service
from app.audit.schemas import AuditLogResponse
from app.auth.models import User
from app.dependencies import get_db
from app.platform_admin.router import require_platform_admin

router = APIRouter()


@router.get("")
async def list_audit_logs(
    _admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: str | None = None,
    result: str | None = None,
    actor_id: uuid.UUID | None = None,
    tenant_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    rows, total = await service.list_audit(
        db,
        action=action,
        result=result,
        actor_id=actor_id,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [AuditLogResponse.from_row(r) for r in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }
