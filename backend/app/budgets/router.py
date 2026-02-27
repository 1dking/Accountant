from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.budgets import service
from app.budgets.models import PeriodType
from app.budgets.schemas import BudgetCreate, BudgetResponse, BudgetUpdate, BudgetVsActual
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


@router.get("")
async def list_budgets(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    year: int | None = Query(None),
    period_type: PeriodType | None = Query(None),
) -> dict:
    budgets, meta = await service.list_budgets(db, year, period_type, pagination)
    return {"data": [BudgetResponse.model_validate(b) for b in budgets], "meta": meta}


@router.get("/vs-actual")
async def budget_vs_actual(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
    month: int | None = Query(None),
) -> dict:
    results = await service.get_budget_vs_actual(db, year, month)
    return {"data": [r.model_dump() for r in results]}


@router.get("/alerts")
async def budget_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    alerts = await service.get_budget_alerts(db)
    return {"data": [a.model_dump() for a in alerts]}


@router.post("", status_code=201)
async def create_budget(
    data: BudgetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    budget = await service.create_budget(db, data, current_user)
    return {"data": BudgetResponse.model_validate(budget)}


@router.get("/{budget_id}")
async def get_budget(
    budget_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    budget = await service.get_budget(db, budget_id)
    return {"data": BudgetResponse.model_validate(budget)}


@router.put("/{budget_id}")
async def update_budget(
    budget_id: uuid.UUID,
    data: BudgetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    budget = await service.update_budget(db, budget_id, data, current_user)
    return {"data": BudgetResponse.model_validate(budget)}


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_budget(db, budget_id)
    return {"data": {"message": "Budget deleted"}}
