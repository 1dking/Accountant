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
