
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.estimates.models import Estimate, EstimateLineItem, EstimateStatus
from app.estimates.schemas import (
    EstimateCreate,
    EstimateFilter,
    EstimateLineItemCreate,
    EstimateUpdate,
)


async def generate_estimate_number(db: AsyncSession) -> str:
    result = await db.execute(
        select(func.count(Estimate.id))
    )
    count = (result.scalar() or 0) + 1
    return f"EST-{count:04d}"


def _calculate_line_total(item: EstimateLineItemCreate) -> float:
    return round(item.quantity * item.unit_price, 2)


def _calculate_estimate_totals(
    line_items: list[EstimateLineItemCreate],
    tax_rate: float | None,
    discount_amount: float,
) -> tuple[float, float | None, float]:
    subtotal = sum(_calculate_line_total(li) for li in line_items)
    tax_amount = round(subtotal * (tax_rate / 100), 2) if tax_rate else None
    total = subtotal + (tax_amount or 0) - discount_amount
    return round(subtotal, 2), tax_amount, round(total, 2)


async def create_estimate(
    db: AsyncSession, data: EstimateCreate, user: User
) -> Estimate:
    estimate_number = await generate_estimate_number(db)
    subtotal, tax_amount, total = _calculate_estimate_totals(
        data.line_items, data.tax_rate, data.discount_amount
    )

    estimate = Estimate(
        estimate_number=estimate_number,
        contact_id=data.contact_id,
        issue_date=data.issue_date,
        expiry_date=data.expiry_date,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        discount_amount=data.discount_amount,
        subtotal=subtotal,
        total=total,
        currency=data.currency,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(estimate)
    await db.flush()

    for li in data.line_items:
        line = EstimateLineItem(
            estimate_id=estimate.id,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            tax_rate=li.tax_rate,
            total=_calculate_line_total(li),
        )
        db.add(line)

    await db.commit()
    await db.refresh(estimate)
    return estimate


async def list_estimates(
    db: AsyncSession, filters: EstimateFilter, pagination: PaginationParams
) -> tuple[list[Estimate], dict]:
    query = select(Estimate).options(selectinload(Estimate.contact))

    if filters.search:
        term = f"%{filters.search}%"
        query = query.where(
            or_(
                Estimate.estimate_number.ilike(term),
                Estimate.notes.ilike(term),
            )
        )
    if filters.status is not None:
        query = query.where(Estimate.status == filters.status)
    if filters.contact_id is not None:
        query = query.where(Estimate.contact_id == filters.contact_id)
    if filters.date_from is not None:
        query = query.where(Estimate.issue_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Estimate.issue_date <= filters.date_to)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Estimate.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    estimates = list(result.scalars().all())

    return estimates, build_pagination_meta(total, pagination)


async def get_estimate(db: AsyncSession, estimate_id: uuid.UUID) -> Estimate:
    result = await db.execute(
        select(Estimate)
        .options(
            selectinload(Estimate.contact),
            selectinload(Estimate.line_items),
        )
        .where(Estimate.id == estimate_id)
    )
    estimate = result.scalar_one_or_none()
    if estimate is None:
        raise NotFoundError("Estimate", str(estimate_id))
    return estimate


async def update_estimate(
    db: AsyncSession, estimate_id: uuid.UUID, data: EstimateUpdate, user: User
) -> Estimate:
    estimate = await get_estimate(db, estimate_id)
    update_data = data.model_dump(exclude_unset=True)
    line_items_data = update_data.pop("line_items", None)

    for key, value in update_data.items():
        setattr(estimate, key, value)

    if line_items_data is not None:
        # Delete old line items
        for li in list(estimate.line_items):
            await db.delete(li)
        # Create new ones
        items = [EstimateLineItemCreate(**li) for li in line_items_data]
        subtotal, tax_amount, total = _calculate_estimate_totals(
            items, estimate.tax_rate, estimate.discount_amount
        )
        estimate.subtotal = subtotal
        estimate.tax_amount = tax_amount
        estimate.total = total

        for li in items:
            line = EstimateLineItem(
                estimate_id=estimate.id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_rate=li.tax_rate,
                total=_calculate_line_total(li),
            )
            db.add(line)

    await db.commit()
    await db.refresh(estimate)
    return estimate


async def delete_estimate(db: AsyncSession, estimate_id: uuid.UUID) -> None:
    estimate = await get_estimate(db, estimate_id)
    await db.delete(estimate)
    await db.commit()


async def convert_to_invoice(
    db: AsyncSession, estimate_id: uuid.UUID, user: User
) -> "Invoice":
    from app.invoicing.models import Invoice, InvoiceLineItem
    from app.invoicing.service import generate_invoice_number

    estimate = await get_estimate(db, estimate_id)

    if estimate.status == EstimateStatus.CONVERTED:
        raise ValidationError("This estimate has already been converted to an invoice.")
    if estimate.status == EstimateStatus.REJECTED:
        raise ValidationError("Cannot convert a rejected estimate to an invoice.")

    invoice_number = await generate_invoice_number(db)

    invoice = Invoice(
        invoice_number=invoice_number,
        contact_id=estimate.contact_id,
        issue_date=date.today(),
        due_date=estimate.expiry_date,
        tax_rate=estimate.tax_rate,
        tax_amount=estimate.tax_amount,
        discount_amount=estimate.discount_amount,
        subtotal=estimate.subtotal,
        total=estimate.total,
        currency=estimate.currency,
        notes=estimate.notes,
        created_by=user.id,
    )
    db.add(invoice)
    await db.flush()

    for li in estimate.line_items:
        line = InvoiceLineItem(
            invoice_id=invoice.id,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            tax_rate=li.tax_rate,
            total=li.total,
        )
        db.add(line)

    estimate.status = EstimateStatus.CONVERTED
    estimate.converted_invoice_id = invoice.id

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def check_expired_estimates(db: AsyncSession) -> int:
    today = date.today()
    result = await db.execute(
        select(Estimate).where(
            Estimate.expiry_date < today,
            Estimate.status.in_([
                EstimateStatus.DRAFT, EstimateStatus.SENT,
            ]),
        )
    )
    estimates = result.scalars().all()
    count = 0
    for est in estimates:
        est.status = EstimateStatus.EXPIRED
        count += 1
    if count:
        await db.commit()
    return count
