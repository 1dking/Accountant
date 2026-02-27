"""Business logic for sales tax tracking."""

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseStatus
from app.accounting.tax_models import TaxRate
from app.accounting.tax_schemas import TaxLiabilityReport, TaxRateCreate, TaxRateUpdate
from app.core.exceptions import ConflictError, NotFoundError
from app.invoicing.models import Invoice, InvoiceStatus


# ---------------------------------------------------------------------------
# TaxRate CRUD
# ---------------------------------------------------------------------------


async def list_tax_rates(db: AsyncSession) -> list[TaxRate]:
    """Return all tax rates ordered by name."""
    result = await db.execute(select(TaxRate).order_by(TaxRate.name))
    return list(result.scalars().all())


async def get_tax_rate(db: AsyncSession, tax_rate_id: str) -> TaxRate:
    """Get a single tax rate by ID."""
    result = await db.execute(select(TaxRate).where(TaxRate.id == tax_rate_id))
    tax_rate = result.scalar_one_or_none()
    if tax_rate is None:
        raise NotFoundError("TaxRate", tax_rate_id)
    return tax_rate


async def create_tax_rate(
    db: AsyncSession,
    data: TaxRateCreate,
    user_id: str,
) -> TaxRate:
    """Create a new tax rate."""
    # If this rate is being set as default, clear any existing default
    if data.is_default:
        await _clear_default_tax_rate(db)

    tax_rate = TaxRate(
        name=data.name,
        rate=data.rate,
        description=data.description,
        is_default=data.is_default,
        region=data.region,
        created_by=user_id,
    )
    db.add(tax_rate)
    await db.commit()
    await db.refresh(tax_rate)
    return tax_rate


async def update_tax_rate(
    db: AsyncSession,
    tax_rate_id: str,
    data: TaxRateUpdate,
) -> TaxRate:
    """Update an existing tax rate."""
    tax_rate = await get_tax_rate(db, tax_rate_id)

    update_data = data.model_dump(exclude_unset=True)

    # If setting as default, clear any existing default first
    if update_data.get("is_default", False):
        await _clear_default_tax_rate(db, exclude_id=tax_rate_id)

    for field, value in update_data.items():
        setattr(tax_rate, field, value)

    await db.commit()
    await db.refresh(tax_rate)
    return tax_rate


async def delete_tax_rate(db: AsyncSession, tax_rate_id: str) -> None:
    """Delete a tax rate."""
    tax_rate = await get_tax_rate(db, tax_rate_id)
    await db.delete(tax_rate)
    await db.commit()


async def _clear_default_tax_rate(
    db: AsyncSession,
    exclude_id: Optional[str] = None,
) -> None:
    """Clear the is_default flag on all tax rates (optionally excluding one)."""
    query = select(TaxRate).where(TaxRate.is_default == True)  # noqa: E712
    if exclude_id is not None:
        query = query.where(TaxRate.id != exclude_id)
    result = await db.execute(query)
    for rate in result.scalars().all():
        rate.is_default = False


# ---------------------------------------------------------------------------
# Tax Liability Report
# ---------------------------------------------------------------------------


async def get_tax_liability_report(
    db: AsyncSession,
    user_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> TaxLiabilityReport:
    """Calculate tax liability from paid invoices and approved expenses."""

    # --- Tax collected: sum of tax_amount on paid invoices ---
    collected_query = select(
        func.coalesce(func.sum(Invoice.tax_amount), 0.0)
    ).where(
        Invoice.status == InvoiceStatus.PAID,
        Invoice.tax_amount.isnot(None),
    )
    if date_from is not None:
        collected_query = collected_query.where(Invoice.issue_date >= date_from)
    if date_to is not None:
        collected_query = collected_query.where(Invoice.issue_date <= date_to)

    total_collected = float(await db.scalar(collected_query) or 0.0)

    # --- Tax paid: sum of tax_amount on approved expenses ---
    paid_query = select(
        func.coalesce(func.sum(Expense.tax_amount), 0.0)
    ).where(
        Expense.status == ExpenseStatus.APPROVED,
        Expense.tax_amount.isnot(None),
    )
    if date_from is not None:
        paid_query = paid_query.where(Expense.date >= date_from)
    if date_to is not None:
        paid_query = paid_query.where(Expense.date <= date_to)

    total_paid = float(await db.scalar(paid_query) or 0.0)

    net_liability = round(total_collected - total_paid, 2)

    return TaxLiabilityReport(
        date_from=date_from.isoformat() if date_from else "",
        date_to=date_to.isoformat() if date_to else "",
        total_tax_collected=round(total_collected, 2),
        total_tax_paid=round(total_paid, 2),
        net_tax_liability=net_liability,
    )
