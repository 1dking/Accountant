"""Personal ledger API — private per-user personal finances (Personal mode).

All endpoints are user-private (service scopes every query to the caller). This
router touches only the personal tables, so business reports are structurally
unaffected. Mounted at /api/personal.
"""
import uuid
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db
from app.personal import service
from app.personal.schemas import (
    PersonalAccountCreate,
    PersonalAccountResponse,
    PersonalAccountUpdate,
    PersonalCashflowSummary,
    PersonalCategoryResponse,
    PersonalTransactionCreate,
    PersonalTransactionResponse,
    PersonalTransactionUpdate,
)

router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


def _txn_response(t) -> PersonalTransactionResponse:
    return PersonalTransactionResponse(
        id=t.id, account_id=t.account_id, date=t.date, direction=t.direction,
        amount=t.amount, description=t.description, category_id=t.category_id,
        category_name=(t.category.name if t.category else None), notes=t.notes,
    )


# --- Categories ------------------------------------------------------------


@router.get("/categories")
async def list_categories(db: DB, user: CurrentUser) -> dict:
    cats = await service.list_categories(db, user)
    return {"data": [PersonalCategoryResponse.model_validate(c) for c in cats]}


# --- Accounts --------------------------------------------------------------


@router.get("/accounts")
async def list_accounts(db: DB, user: CurrentUser) -> dict:
    accts = await service.list_accounts(db, user)
    out = []
    for a in accts:
        resp = PersonalAccountResponse.model_validate(a)
        resp.current_balance = await service.account_balance(db, user, a)
        out.append(resp)
    return {"data": out}


@router.post("/accounts", status_code=201)
async def create_account(data: PersonalAccountCreate, db: DB, user: CurrentUser) -> dict:
    acct = await service.create_account(db, user, data)
    return {"data": PersonalAccountResponse.model_validate(acct)}


@router.put("/accounts/{account_id}")
async def update_account(account_id: uuid.UUID, data: PersonalAccountUpdate, db: DB, user: CurrentUser) -> dict:
    acct = await service.update_account(db, user, account_id, data)
    return {"data": PersonalAccountResponse.model_validate(acct)}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    await service.delete_account(db, user, account_id)
    return {"data": {"detail": "deleted"}}


# --- Transactions ----------------------------------------------------------


@router.get("/transactions")
async def list_transactions(
    db: DB, user: CurrentUser,
    account_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    txns = await service.list_transactions(
        db, user, account_id=account_id, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return {"data": [_txn_response(t) for t in txns]}


@router.post("/transactions", status_code=201)
async def create_transaction(data: PersonalTransactionCreate, db: DB, user: CurrentUser) -> dict:
    txn = await service.create_transaction(db, user, data)
    return {"data": _txn_response(txn)}


@router.put("/transactions/{txn_id}")
async def update_transaction(txn_id: uuid.UUID, data: PersonalTransactionUpdate, db: DB, user: CurrentUser) -> dict:
    txn = await service.update_transaction(db, user, txn_id, data)
    return {"data": _txn_response(txn)}


@router.delete("/transactions/{txn_id}")
async def delete_transaction(txn_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    await service.delete_transaction(db, user, txn_id)
    return {"data": {"detail": "deleted"}}


# --- Cashflow --------------------------------------------------------------


@router.get("/cashflow")
async def cashflow(
    db: DB, user: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    summary = await service.cashflow_summary(db, user, date_from=date_from, date_to=date_to)
    return {"data": PersonalCashflowSummary.model_validate(summary)}
