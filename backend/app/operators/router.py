"""Operator (agency) API — /api/operators. Admin-only; service enforces the
'not inside a sub-account' rule. No business-mode gate: this is agency tooling."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_db, require_role
from app.operators import service
from app.operators.schemas import FeatureSet, MemberInvite, SubAccountCreate, SubAccountUpdate

router = APIRouter()

_DB = Annotated[AsyncSession, Depends(get_db)]
_Op = Annotated[User, Depends(require_role([Role.ADMIN]))]


@router.get("/templates")
async def list_templates(_: _Op) -> dict:
    return {"data": [t.model_dump(mode="json") for t in service.templates()]}


@router.get("/sub-accounts")
async def list_sub_accounts(db: _DB, user: _Op) -> dict:
    return {"data": [s.model_dump(mode="json") for s in await service.list_sub_accounts(db, user)]}


@router.post("/sub-accounts", status_code=201)
async def create_sub_account(data: SubAccountCreate, db: _DB, user: _Op) -> dict:
    return {"data": (await service.create_sub_account(db, user, data)).model_dump(mode="json")}


@router.get("/sub-accounts/{sub_account_id}")
async def get_sub_account(sub_account_id: uuid.UUID, db: _DB, user: _Op) -> dict:
    return {"data": (await service.get_sub_account(db, user, sub_account_id)).model_dump(mode="json")}


@router.put("/sub-accounts/{sub_account_id}")
async def update_sub_account(sub_account_id: uuid.UUID, data: SubAccountUpdate, db: _DB, user: _Op) -> dict:
    return {"data": (await service.update_sub_account(db, user, sub_account_id, data)).model_dump(mode="json")}


@router.put("/sub-accounts/{sub_account_id}/features/{feature_key}")
async def set_feature(sub_account_id: uuid.UUID, feature_key: str, body: FeatureSet, db: _DB, user: _Op) -> dict:
    return {"data": (await service.set_feature(db, user, sub_account_id, feature_key, body.enabled)).model_dump(mode="json")}


@router.post("/sub-accounts/{sub_account_id}/books/unlock")
async def unlock_books(sub_account_id: uuid.UUID, db: _DB, user: _Op) -> dict:
    return {"data": (await service.set_books(db, user, sub_account_id, True)).model_dump(mode="json")}


@router.post("/sub-accounts/{sub_account_id}/books/lock")
async def lock_books(sub_account_id: uuid.UUID, db: _DB, user: _Op) -> dict:
    return {"data": (await service.set_books(db, user, sub_account_id, False)).model_dump(mode="json")}


@router.get("/sub-accounts/{sub_account_id}/members")
async def list_members(sub_account_id: uuid.UUID, db: _DB, user: _Op) -> dict:
    return {"data": [m.model_dump(mode="json") for m in await service.list_members(db, user, sub_account_id)]}


@router.post("/sub-accounts/{sub_account_id}/members", status_code=201)
async def invite_member(sub_account_id: uuid.UUID, data: MemberInvite, db: _DB, user: _Op) -> dict:
    return {"data": (await service.invite_member(db, user, sub_account_id, data)).model_dump(mode="json")}
