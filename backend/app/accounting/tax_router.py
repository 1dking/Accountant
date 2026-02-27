"""FastAPI router for sales tax tracking."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import tax_service
from app.accounting.tax_schemas import (
    TaxLiabilityReport,
    TaxRateCreate,
    TaxRateResponse,
    TaxRateUpdate,
)
from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Tax Rate CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/accounting/tax-rates")
async def list_tax_rates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return all configured tax rates."""
    rates = await tax_service.list_tax_rates(db)
    return {"data": [TaxRateResponse.model_validate(r) for r in rates]}


@router.post("/accounting/tax-rates", status_code=201)
async def create_tax_rate(
    data: TaxRateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Create a new tax rate (admin only)."""
    try:
        rate = await tax_service.create_tax_rate(
            db, data, user_id=str(current_user.id)
        )
        return {"data": TaxRateResponse.model_validate(rate)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/accounting/tax-rates/{tax_rate_id}")
async def update_tax_rate(
    tax_rate_id: str,
    data: TaxRateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Update an existing tax rate (admin only)."""
    rate = await tax_service.update_tax_rate(db, tax_rate_id, data)
    return {"data": TaxRateResponse.model_validate(rate)}


@router.delete("/accounting/tax-rates/{tax_rate_id}")
async def delete_tax_rate(
    tax_rate_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Delete a tax rate (admin only)."""
    await tax_service.delete_tax_rate(db, tax_rate_id)
    return {"data": {"detail": "Tax rate deleted successfully"}}


# ---------------------------------------------------------------------------
# Tax Liability Report endpoint
# ---------------------------------------------------------------------------


@router.get("/accounting/tax-liability")
async def get_tax_liability(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Get the tax liability report for a date range."""
    report = await tax_service.get_tax_liability_report(
        db,
        user_id=str(current_user.id),
        date_from=date_from,
        date_to=date_to,
    )
    return {"data": report.model_dump()}
