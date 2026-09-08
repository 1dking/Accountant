"""Domain reseller HTTP router — mounted at /api/domains."""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.domains import service
from app.domains.porkbun import PorkbunError
from app.domains.migadu import MigaduError

logger = logging.getLogger(__name__)
router = APIRouter()


class CheckReq(BaseModel):
    domain: str


class PurchaseReq(BaseModel):
    domain: str
    years: int = Field(default=1, ge=1, le=10)


class DnsReq(BaseModel):
    type: str
    content: str
    name: str = ""
    ttl: int = 600
    priority: int | None = None
    record_id: str | None = None


class MailboxReq(BaseModel):
    local_part: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=12, max_length=256)


class PasswordReq(BaseModel):
    password: str = Field(..., min_length=12, max_length=256)


def _settings(request: Request):
    return request.app.state.settings


@router.post("/check")
async def check_domain(
    body: CheckReq,
    request: Request,
    _: Annotated[User, Depends(get_current_user)],
):
    return {"data": await service.check_domain(body.domain, _settings(request))}


@router.post("/purchase")
async def purchase(
    body: PurchaseReq,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    base_url = str(request.base_url)
    try:
        return {"data": await service.create_purchase_checkout(
            db, user, _settings(request),
            domain=body.domain, years=body.years, base_url=base_url,
        )}
    except PorkbunError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("")
async def list_purchases(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rows = await service.list_purchases(db, user)
    return {"data": [_serialize(r) for r in rows]}


@router.get("/{purchase_id}")
async def get_purchase(
    purchase_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    row = await service.get_purchase(db, user, purchase_id)
    return {"data": _serialize(row)}


@router.get("/{purchase_id}/dns")
async def list_dns(
    purchase_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return {"data": await service.list_dns(db, user, _settings(request), purchase_id)}
    except PorkbunError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{purchase_id}/dns")
async def upsert_dns(
    purchase_id: uuid.UUID,
    body: DnsReq,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.upsert_dns(
            db, user, _settings(request), purchase_id,
            record_id=body.record_id, type=body.type, content=body.content,
            name=body.name, ttl=body.ttl, priority=body.priority,
        )}
    except PorkbunError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/{purchase_id}/dns/{record_id}")
async def delete_dns(
    purchase_id: uuid.UUID,
    record_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.delete_dns(
            db, user, _settings(request), purchase_id, record_id,
        )}
    except PorkbunError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Email hosting (Migadu)
# ---------------------------------------------------------------------------

@router.post("/{purchase_id}/email/enable")
async def enable_email(
    purchase_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.enable_email(db, user, _settings(request), purchase_id)}
    except (MigaduError, PorkbunError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{purchase_id}/mailboxes")
async def list_mailboxes(
    purchase_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return {"data": await service.list_mailboxes(db, user, _settings(request), purchase_id)}
    except MigaduError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{purchase_id}/mailboxes")
async def create_mailbox(
    purchase_id: uuid.UUID,
    body: MailboxReq,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.create_mailbox(
            db, user, _settings(request), purchase_id,
            local_part=body.local_part, name=body.name, password=body.password,
        )}
    except MigaduError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.put("/{purchase_id}/mailboxes/{local_part}/password")
async def reset_mailbox_password(
    purchase_id: uuid.UUID,
    local_part: str,
    body: PasswordReq,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.reset_mailbox_password(
            db, user, _settings(request), purchase_id,
            local_part=local_part, password=body.password,
        )}
    except MigaduError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/{purchase_id}/mailboxes/{local_part}")
async def delete_mailbox(
    purchase_id: uuid.UUID,
    local_part: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
):
    try:
        return {"data": await service.delete_mailbox(
            db, user, _settings(request), purchase_id, local_part,
        )}
    except MigaduError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _serialize(row) -> dict:
    return {
        "id": str(row.id),
        "domain": row.domain,
        "tld": row.tld,
        "status": row.status,
        "years": row.years,
        "price_cents_paid": row.price_cents_paid,
        "price_cents_wholesale": row.price_cents_wholesale,
        "currency": row.currency,
        "registered_at": row.registered_at.isoformat() if row.registered_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "auto_renew": row.auto_renew,
        "partner": row.partner,
        "email_enabled": bool(row.email_enabled),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
