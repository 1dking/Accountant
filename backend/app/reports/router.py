
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db
from app.reports import service
from app.reports.pdf import generate_profit_loss_pdf, generate_quarterly_tax_pdf, generate_tax_summary_pdf

router = APIRouter()


@router.get("/profit-loss")
async def profit_loss(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> dict:
    report = await service.get_profit_loss(db, date_from, date_to)
    return {"data": report.model_dump()}


@router.get("/profit-loss/pdf")
async def profit_loss_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> Response:
    report = await service.get_profit_loss(db, date_from, date_to)
    pdf_bytes = generate_profit_loss_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pnl-{date_from}-{date_to}.pdf"'},
    )


@router.get("/tax-summary")
async def tax_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
) -> dict:
    report = await service.get_tax_summary(db, year)
    return {"data": report.model_dump()}


@router.get("/tax-summary/pdf")
async def tax_summary_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
) -> Response:
    report = await service.get_tax_summary(db, year)
    pdf_bytes = generate_tax_summary_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="tax-summary-{year}.pdf"'},
    )


@router.get("/cash-flow")
async def cash_flow(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> dict:
    report = await service.get_cash_flow(db, date_from, date_to)
    return {"data": report.model_dump()}


@router.get("/accounts-summary")
async def accounts_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    summary = await service.get_accounts_summary(db)
    return {"data": summary.model_dump()}


@router.get("/ar-aging")
async def ar_aging(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    as_of_date: Optional[date] = Query(None),
) -> dict:
    if as_of_date is None:
        as_of_date = date.today()
    report = await service.get_ar_aging(db, as_of_date)
    return {"data": report.model_dump()}


@router.get("/ap-aging")
async def ap_aging(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    as_of_date: Optional[date] = Query(None),
) -> dict:
    if as_of_date is None:
        as_of_date = date.today()
    report = await service.get_ap_aging(db, as_of_date)
    return {"data": report.model_dump()}


@router.get("/tax-quarterly")
async def quarterly_tax_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
    tax_rate: float = Query(25.0, ge=0, le=100),
) -> dict:
    report = await service.get_quarterly_tax_report(db, year, tax_rate)
    return {"data": report.model_dump()}


@router.get("/tax-quarterly/pdf")
async def quarterly_tax_report_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
    tax_rate: float = Query(25.0, ge=0, le=100),
) -> Response:
    report = await service.get_quarterly_tax_report(db, year, tax_rate)
    pdf_bytes = generate_quarterly_tax_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="quarterly-tax-{year}.pdf"'},
    )


@router.get("/year-over-year")
async def year_over_year(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
) -> dict:
    comparison = await service.get_year_over_year(db, year)
    return {"data": comparison.model_dump()}


@router.get("/tax-deadlines")
async def tax_deadlines(
    _: Annotated[User, Depends(get_current_user)],
    year: int = Query(...),
) -> dict:
    deadlines = service.get_tax_deadlines(year)
    return {"data": [d.model_dump() for d in deadlines]}
