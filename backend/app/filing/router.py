"""Joint filing API. Any authenticated user; the personal half is owner-only
by construction (see service.filing_package). Mounted WITHOUT
require_business_mode so the package is reachable from Personal mode too —
it reads both ledgers by design."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db
from app.filing import service
from app.filing.schemas import FilingPackage, T2125Statement

router = APIRouter()

_DB = Annotated[AsyncSession, Depends(get_db)]
_User = Annotated[User, Depends(get_current_user)]


@router.get("/package")
async def get_package(db: _DB, user: _User, year: int | None = Query(None)) -> dict:
    pkg: FilingPackage = await service.filing_package(db, user, year or date.today().year)
    return {"data": pkg.model_dump(mode="json")}


@router.get("/t2125")
async def get_t2125(db: _DB, user: _User, year: int | None = Query(None)) -> dict:
    out: T2125Statement = await service.t2125_statement(db, user, year or date.today().year)
    return {"data": out.model_dump(mode="json")}


@router.get("/package/pdf")
async def get_package_pdf(request: Request, db: _DB, user: _User, year: int | None = Query(None)) -> Response:
    from app.filing.pdf import generate_filing_pdf
    from app.payroll.router import _company_ctx

    y = year or date.today().year
    pkg = await service.filing_package(db, user, y)
    company, logo = await _company_ctx(request, db)
    pdf = generate_filing_pdf(pkg, company, logo)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="tax-filing-{y}.pdf"'})
