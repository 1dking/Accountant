"""FastAPI router for the Chart of Accounts."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service
from app.accounting.coa_schemas import (
    ChartAccountCreate,
    ChartAccountResponse,
    ChartAccountUpdate,
    CoASeedResult,
)
from app.accounting.ledger_models import AccountType
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


@router.get("/accounts")
async def list_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    account_type: AccountType | None = None,
    include_inactive: bool = Query(default=False),
) -> dict:
    """List the tenant's Chart of Accounts, ordered by code."""
    accounts = await coa_service.list_accounts(
        db, user, account_type=account_type, include_inactive=include_inactive
    )
    return {"data": [ChartAccountResponse.model_validate(a) for a in accounts]}


@router.post("/accounts/seed", status_code=201)
async def seed_chart_of_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    migrate: bool = Query(default=True),
) -> dict:
    """Seed the standard CoA for this tenant and migrate the flat cashbook onto
    it. Idempotent — safe to call more than once."""
    result: CoASeedResult = await coa_service.seed_default_coa(db, user, migrate=migrate)
    return {"data": result}


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    account = await coa_service.get_account(db, account_id, user)
    return {"data": ChartAccountResponse.model_validate(account)}


@router.post("/accounts", status_code=201)
async def create_account(
    data: ChartAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    account = await coa_service.create_account(db, data, user)
    return {"data": ChartAccountResponse.model_validate(account)}


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: uuid.UUID,
    data: ChartAccountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    account = await coa_service.update_account(db, account_id, data, user)
    return {"data": ChartAccountResponse.model_validate(account)}


@router.delete("/accounts/{account_id}")
async def deactivate_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Deactivate (soft-delete) an account. Accounts are never hard-deleted
    because journal lines reference them."""
    account = await coa_service.deactivate_account(db, account_id, user)
    return {"data": ChartAccountResponse.model_validate(account)}
