"""FastAPI router for the General Ledger and Trial Balance reports."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


def _money(obj):
    """Recursively stringify Decimals so money crosses the wire as fixed-point."""
    if isinstance(obj, Decimal):
        return f"{obj:.2f}"
    if isinstance(obj, dict):
        return {k: _money(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_money(v) for v in obj]
    return obj


@router.get("/reports/trial-balance")
async def get_trial_balance(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    postings = await ledger_reports.gather_postings(db, user, date_from=date_from, date_to=date_to)
    return {"data": _money(ledger_reports.trial_balance(postings))}


@router.get("/reports/general-ledger")
async def get_general_ledger(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    postings = await ledger_reports.gather_postings(db, user, date_from=date_from, date_to=date_to)
    return {"data": _money(ledger_reports.general_ledger(postings))}


@router.get("/reports/profit-loss")
async def get_profit_loss(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Cashbook-consistent Income Statement over the period."""
    postings = await ledger_reports.gather_postings(db, user, date_from=date_from, date_to=date_to)
    return {"data": _money(ledger_reports.profit_loss(postings))}


@router.get("/reports/balance-sheet")
async def get_balance_sheet(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    as_of: date | None = None,
) -> dict:
    """Assets / Liabilities / Equity as of a date (inception → as_of), with
    opening balances folded in so it ties to the cashbook and balances."""
    postings = await ledger_reports.gather_postings(db, user, date_to=as_of, include_opening=True)
    result = ledger_reports.balance_sheet(postings)
    result["as_of"] = (as_of or date.today()).isoformat()
    return {"data": _money(result)}
