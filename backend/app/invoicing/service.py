from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.invoicing.models import Invoice, InvoiceLineItem, InvoicePayment, InvoiceStatus
from app.invoicing.schemas import (
    InvoiceCreate,
    InvoiceFilter,
    InvoiceLineItemCreate,
    InvoicePaymentCreate,
    InvoiceUpdate,
)


async def generate_invoice_number(db: AsyncSession) -> str:
    result = await db.execute(
        select(func.count(Invoice.id))
    )
    count = (result.scalar() or 0) + 1
    return f"INV-{count:04d}"


def _calculate_line_total(item: InvoiceLineItemCreate) -> float:
    return round(item.quantity * item.unit_price, 2)


def _calculate_invoice_totals(
    line_items: list[InvoiceLineItemCreate],
    tax_rate: float | None,
    discount_amount: float,
) -> tuple[float, float | None, float]:
    subtotal = sum(_calculate_line_total(li) for li in line_items)
    tax_amount = round(subtotal * (tax_rate / 100), 2) if tax_rate else None
    total = subtotal + (tax_amount or 0) - discount_amount
    return round(subtotal, 2), tax_amount, round(total, 2)


async def create_invoice(
    db: AsyncSession, data: InvoiceCreate, user: User
) -> Invoice:
    invoice_number = await generate_invoice_number(db)
    subtotal, tax_amount, total = _calculate_invoice_totals(
        data.line_items, data.tax_rate, data.discount_amount
    )

    invoice = Invoice(
        invoice_number=invoice_number,
        contact_id=data.contact_id,
        issue_date=data.issue_date,
        due_date=data.due_date,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        discount_amount=data.discount_amount,
        subtotal=subtotal,
        total=total,
        currency=data.currency,
        notes=data.notes,
        payment_terms=data.payment_terms,
        created_by=user.id,
    )
    db.add(invoice)
    await db.flush()

    for li in data.line_items:
        line = InvoiceLineItem(
            invoice_id=invoice.id,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            tax_rate=li.tax_rate,
            total=_calculate_line_total(li),
        )
        db.add(line)

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def list_invoices(
    db: AsyncSession, filters: InvoiceFilter, pagination: PaginationParams
) -> tuple[list[Invoice], dict]:
    query = select(Invoice).options(selectinload(Invoice.contact))

    if filters.search:
        term = f"%{filters.search}%"
        query = query.where(
            or_(
                Invoice.invoice_number.ilike(term),
                Invoice.notes.ilike(term),
            )
        )
    if filters.status is not None:
        query = query.where(Invoice.status == filters.status)
    if filters.contact_id is not None:
        query = query.where(Invoice.contact_id == filters.contact_id)
    if filters.date_from is not None:
        query = query.where(Invoice.issue_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Invoice.issue_date <= filters.date_to)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Invoice.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    invoices = list(result.scalars().all())

    return invoices, build_pagination_meta(total, pagination)


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    result = await db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.contact),
            selectinload(Invoice.line_items),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice", str(invoice_id))
    return invoice


async def update_invoice(
    db: AsyncSession, invoice_id: uuid.UUID, data: InvoiceUpdate, user: User
) -> Invoice:
    invoice = await get_invoice(db, invoice_id)
    update_data = data.model_dump(exclude_unset=True)
    line_items_data = update_data.pop("line_items", None)

    for key, value in update_data.items():
        setattr(invoice, key, value)

    if line_items_data is not None:
        # Delete old line items
        for li in list(invoice.line_items):
            await db.delete(li)
        # Create new ones
        items = [InvoiceLineItemCreate(**li) for li in line_items_data]
        subtotal, tax_amount, total = _calculate_invoice_totals(
            items, invoice.tax_rate, invoice.discount_amount
        )
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.total = total

        for li in items:
            line = InvoiceLineItem(
                invoice_id=invoice.id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_rate=li.tax_rate,
                total=_calculate_line_total(li),
            )
            db.add(line)

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def delete_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> None:
    invoice = await get_invoice(db, invoice_id)
    await db.delete(invoice)
    await db.commit()


async def send_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    invoice = await get_invoice(db, invoice_id)
    if invoice.status not in (InvoiceStatus.DRAFT,):
        raise ValidationError("Only draft invoices can be sent.")
    invoice.status = InvoiceStatus.SENT
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def record_payment(
    db: AsyncSession, invoice_id: uuid.UUID, data: InvoicePaymentCreate, user: User
) -> InvoicePayment:
    invoice = await get_invoice(db, invoice_id)

    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=data.amount,
        date=data.date,
        payment_method=data.payment_method,
        reference=data.reference,
        notes=data.notes,
        recorded_by=user.id,
    )
    db.add(payment)

    # Update invoice status based on total payments
    total_paid = sum(p.amount for p in invoice.payments) + data.amount
    if total_paid >= invoice.total:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    await db.commit()
    await db.refresh(payment)

    # Auto-create income entry
    try:
        from app.income.service import create_income_from_payment
        await create_income_from_payment(db, invoice, payment, user)
    except ImportError:
        pass  # Income module not yet available

    return payment


async def get_invoice_stats(db: AsyncSession) -> dict:
    now = date.today()

    outstanding_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID])
    )
    total_outstanding = (await db.execute(outstanding_q)).scalar() or 0

    overdue_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    total_overdue = (await db.execute(overdue_q)).scalar() or 0

    paid_q = select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(
        func.extract("year", InvoicePayment.date) == now.year,
        func.extract("month", InvoicePayment.date) == now.month,
    )
    total_paid = (await db.execute(paid_q)).scalar() or 0

    count_q = select(func.count(Invoice.id))
    invoice_count = (await db.execute(count_q)).scalar() or 0

    return {
        "total_outstanding": float(total_outstanding),
        "total_overdue": float(total_overdue),
        "total_paid_this_month": float(total_paid),
        "invoice_count": invoice_count,
    }


async def check_overdue_invoices(db: AsyncSession) -> int:
    today = date.today()
    result = await db.execute(
        select(Invoice).where(
            Invoice.due_date < today,
            Invoice.status.in_([
                InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID
            ]),
        )
    )
    invoices = result.scalars().all()
    count = 0
    for inv in invoices:
        inv.status = InvoiceStatus.OVERDUE
        count += 1
    if count:
        await db.commit()
    return count
