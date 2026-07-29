"""FastAPI router for the General Ledger and Trial Balance reports."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports, statement_pdf
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


async def _business_name(db: AsyncSession, user: User) -> str:
    """Header name for exports: the org name if the user is in one, else their
    own name, else a neutral fallback."""
    if getattr(user, "org_id", None):
        from app.platform_admin.models import Organization
        name = (await db.execute(
            select(Organization.name).where(Organization.id == user.org_id)
        )).scalar_one_or_none()
        if name:
            return name
    return (user.full_name or "").strip() or "Financial Statements"


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


@router.get("/reports/profit-loss.pdf")
async def profit_loss_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    """Downloadable P&L — the cashbook-consistent statement, ready for an accountant."""
    postings = await ledger_reports.gather_postings(db, user, date_from=date_from, date_to=date_to)
    pl = ledger_reports.profit_loss(postings)
    pdf = statement_pdf.generate_profit_loss_pdf(
        pl, date_from=date_from, date_to=date_to,
        business_name=await _business_name(db, user),
    )
    stamp = (date_to or date.today()).isoformat()
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="profit-and-loss_{stamp}.pdf"'},
    )


@router.get("/reports/balance-sheet.pdf")
async def balance_sheet_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    as_of: date | None = None,
) -> Response:
    """Downloadable Balance Sheet — folds in opening balances so it ties out."""
    postings = await ledger_reports.gather_postings(db, user, date_to=as_of, include_opening=True)
    bs = ledger_reports.balance_sheet(postings)
    as_of_str = (as_of or date.today()).isoformat()
    pdf = statement_pdf.generate_balance_sheet_pdf(
        bs, as_of=as_of_str, business_name=await _business_name(db, user),
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="balance-sheet_{as_of_str}.pdf"'},
    )
