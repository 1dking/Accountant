"""FastAPI router for 1099 / contractor tracking."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import tax1099_service
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


class Set1099Flag(BaseModel):
    is_1099_vendor: bool


def _money(obj):
    if isinstance(obj, Decimal):
        return f"{obj:.2f}"
    if isinstance(obj, dict):
        return {k: _money(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_money(v) for v in obj]
    return obj


@router.get("/1099/report")
async def report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    year: int,
) -> dict:
    data = await tax1099_service.get_1099_report(db, user, year)
    return {"data": _money(data)}


@router.post("/1099/vendors/{contact_id}")
async def set_flag(
    contact_id: uuid.UUID,
    body: Set1099Flag,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    contact = await tax1099_service.set_1099_flag(db, user, contact_id, body.is_1099_vendor)
    return {"data": {"contact_id": str(contact.id), "is_1099_vendor": contact.is_1099_vendor}}
