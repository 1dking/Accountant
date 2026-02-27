
import uuid
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role
from app.income import service
from app.income.models import IncomeCategory
from app.income.schemas import (
    IncomeCreate,
    IncomeFilter,
    IncomeListItem,
    IncomeResponse,
    IncomeUpdate,
)

router = APIRouter()


@router.get("")
async def list_income(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    category: IncomeCategory | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> dict:
    filters = IncomeFilter(
        search=search, category=category, contact_id=contact_id,
        date_from=date_from, date_to=date_to,
    )
    entries, meta = await service.list_income(db, filters, pagination)
    return {"data": [IncomeListItem.model_validate(e) for e in entries], "meta": meta}


@router.get("/summary")
async def income_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> dict:
    summary = await service.get_income_summary(db, date_from, date_to)
    return {"data": summary.model_dump()}


@router.post("", status_code=201)
async def create_income(
    data: IncomeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    income = await service.create_income(db, data, current_user)
    return {"data": IncomeResponse.model_validate(income)}


@router.get("/{income_id}")
async def get_income(
    income_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    income = await service.get_income(db, income_id)
    return {"data": IncomeResponse.model_validate(income)}


@router.put("/{income_id}")
async def update_income(
    income_id: uuid.UUID,
    data: IncomeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    income = await service.update_income(db, income_id, data, current_user)
    return {"data": IncomeResponse.model_validate(income)}


@router.delete("/{income_id}")
async def delete_income(
    income_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_income(db, income_id)
    return {"data": {"message": "Income entry deleted"}}
