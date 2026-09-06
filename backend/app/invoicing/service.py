
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.collaboration.service import log_activity
from app.core.authorization import apply_visibility_filter, authorize_record
from app.core.exceptions import NotFoundError, ValidationError
from app.events.service import emit_event, resolve_org_id
from app.core.pagination import PaginationParams, build_pagination_meta
from app.invoicing.models import Invoice, InvoiceLineItem, InvoicePayment, InvoiceStatus
from app.invoicing.schemas import (
    InvoiceCreate,
    InvoiceFilter,
    InvoiceLineItemCreate,
    InvoicePaymentCreate,
    InvoiceUpdate,
)

logger = logging.getLogger(__name__)


async def generate_invoice_number(db: AsyncSession) -> str:
    """Generate the next sequential invoice number.

    Uses ``FOR UPDATE`` on the latest row to serialise concurrent inserts,
    preventing duplicate invoice numbers under parallel requests.
    """
    result = await db.execute(
        select(Invoice.invoice_number)
        .order_by(Invoice.invoice_number.desc())
        .limit(1)
        .with_for_update()
    )
    last = result.scalar()
    if last:
        num = int(last.split("-")[1]) + 1
    else:
        num = 1
    return f"INV-{num:04d}"


def _calculate_line_total(item: InvoiceLineItemCreate) -> Decimal:
    return (Decimal(str(item.quantity)) * Decimal(str(item.unit_price))).quantize(Decimal('0.01'))


def _calculate_invoice_totals(
    line_items: list[InvoiceLineItemCreate],
    tax_rate: float | None,
    discount_amount: float,
) -> tuple[Decimal, Decimal | None, Decimal]:
    subtotal = sum((_calculate_line_total(li) for li in line_items), Decimal('0'))
    tax_amount = (subtotal * (Decimal(str(tax_rate)) / Decimal('100'))).quantize(Decimal('0.01')) if tax_rate else None
    total = subtotal + (tax_amount or Decimal('0')) - Decimal(str(discount_amount))
    return subtotal.quantize(Decimal('0.01')), tax_amount, total.quantize(Decimal('0.01'))


class _ResolvedTax:
    """What an invoice's tax resolved to — the combined rate plus the split.

    ``rate`` is the percentage stored in ``Invoice.tax_rate`` (backward compat).
    When the caller supplied an explicit ``tax_rate`` we keep it single-scalar
    and leave the split NULL (pre-matrix semantics: readers treat it as all-CRA).
    When they didn't, the company's province decides, and we record which
    system rates were used so the invoice PDF can print "GST 5% + PST 7%".
    """

    __slots__ = ("rate", "gst_hst", "pst", "rate_id", "rate_2_id", "rate_2")

    def __init__(self):
        self.rate: float | None = None
        self.gst_hst: Decimal | None = None
        self.pst: Decimal | None = None
        self.rate_id: str | None = None
        self.rate_2_id: str | None = None
        self.rate_2: float | None = None


async def _resolve_invoice_tax(db: AsyncSession, explicit_rate: float | None) -> _ResolvedTax:
    """Province-aware tax resolution for an invoice.

    Explicit rate -> honoured as-is, no split. No rate -> the company's province
    (canadian_tax.rates_for_province) supplies (primary, secondary).
    """
    from app.accounting import canadian_tax
    from app.settings.service import get_company_settings

    out = _ResolvedTax()
    if explicit_rate is not None:
        out.rate = explicit_rate
        return out

    company = await get_company_settings(db)
    if not company or not company.province:
        return out
    primary, secondary = await canadian_tax.rates_for_province(db, company.province)
    if primary is None:
        return out
    out.rate = canadian_tax.combined_rate(primary, secondary)
    out.rate_id = primary.id
    out.rate_2_id = secondary.id if secondary else None
    out.rate_2 = float(secondary.rate) if secondary else None
    return out


def _apply_split(
    subtotal: Decimal, resolved: _ResolvedTax
) -> tuple[Decimal | None, Decimal | None]:
    """(gst_hst, pst) on a tax-EXCLUSIVE subtotal, or (None, None) when the
    invoice isn't province-resolved."""
    if resolved.rate_id is None:
        return None, None
    from app.accounting import canadian_tax
    # Re-derive the pair from the recorded ids' rates without another query:
    # gst_hst = subtotal × primary; pst = subtotal × secondary. The primary's
    # rate is combined − secondary.
    combined = Decimal(str(resolved.rate or 0))
    sec = Decimal(str(resolved.rate_2 or 0))
    prim = combined - sec
    cra = (subtotal * prim / Decimal("100")).quantize(Decimal("0.01"))
    prov = (subtotal * sec / Decimal("100")).quantize(Decimal("0.01"))
    return cra, prov


async def create_invoice(
    db: AsyncSession, data: InvoiceCreate, user: User
) -> Invoice:
    # Ensure the accounting period is open for the issue date
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, data.issue_date)

    resolved = await _resolve_invoice_tax(db, data.tax_rate)
    subtotal, tax_amount, total = _calculate_invoice_totals(
        data.line_items, resolved.rate, data.discount_amount
    )
    gst_hst, pst = _apply_split(subtotal, resolved)

    # Retry loop handles the race condition when the invoices table is empty:
    # FOR UPDATE cannot lock non-existent rows, so concurrent inserts may
    # generate the same invoice number.  On IntegrityError we re-generate
    # the number inside a SAVEPOINT so the outer transaction stays valid.
    max_retries = 5
    invoice = None
    for attempt in range(max_retries):
        invoice_number = await generate_invoice_number(db)
        invoice = Invoice(
            invoice_number=invoice_number,
            contact_id=data.contact_id,
            issue_date=data.issue_date,
            due_date=data.due_date,
            tax_rate=resolved.rate,
            tax_amount=tax_amount,
            tax_gst_hst_amount=gst_hst,
            tax_pst_amount=pst,
            tax_rate_id=resolved.rate_id,
            tax_rate_2_id=resolved.rate_2_id,
            discount_amount=data.discount_amount,
            subtotal=subtotal,
            total=total,
            currency=data.currency,
            notes=data.notes,
            payment_terms=data.payment_terms,
            created_by=user.id,
        )
        nested = await db.begin_nested()
        try:
            db.add(invoice)
            await db.flush()
            break
        except IntegrityError:
            await nested.rollback()
            if attempt == max_retries - 1:
                raise

    for li in data.line_items:
        line = InvoiceLineItem(
            invoice_id=invoice.id,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            # Province-resolved invoices stamp the pair on every line so the PDF
            # can print per-line "GST 5% + PST 7%"; explicit-rate invoices keep
            # whatever the caller put on the line.
            tax_rate=li.tax_rate if resolved.rate_id is None else resolved.rate,
            tax_rate_2=resolved.rate_2,
            tax_rate_id=resolved.rate_id,
            tax_rate_2_id=resolved.rate_2_id,
            total=_calculate_line_total(li),
        )
        db.add(line)

    await db.commit()
    await db.refresh(invoice)

    await log_activity(
        db,
        user_id=user.id,
        action="invoice_created",
        resource_type="invoice",
        resource_id=str(invoice.id),
        details={"invoice_number": invoice.invoice_number, "total": invoice.total},
    )

    from app.workflows.models import TriggerType
    from app.workflows.service import safe_dispatch

    await safe_dispatch(
        db,
        TriggerType.INVOICE_CREATED,
        event_data={
            "invoice_number": invoice.invoice_number,
            "total": float(invoice.total),
        },
        contact_id=invoice.contact_id,
    )

    return invoice


async def list_invoices(
    db: AsyncSession, filters: InvoiceFilter, pagination: PaginationParams, user: User
) -> tuple[list[Invoice], dict]:
    query = select(Invoice).options(selectinload(Invoice.contact))
    query = apply_visibility_filter(query, Invoice.created_by, user, contact_col=Invoice.contact_id)

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


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID, user: User) -> Invoice:
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
    await authorize_record(
        db, user, invoice.created_by, contact_id=invoice.contact_id, resource_name="Invoice"
    )
    return invoice


async def update_invoice(
    db: AsyncSession, invoice_id: uuid.UUID, data: InvoiceUpdate, user: User
) -> Invoice:
    invoice = await get_invoice(db, invoice_id, user)

    # Check the current invoice date's period and the new date's period (if changing)
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, invoice.issue_date)
    if data.issue_date is not None and data.issue_date != invoice.issue_date:
        await assert_period_open(db, data.issue_date)

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
        # Re-resolve: a province-resolved invoice (has tax_rate_id) keeps
        # following the province; an explicit-rate invoice keeps its rate.
        resolved = await _resolve_invoice_tax(
            db, None if invoice.tax_rate_id else invoice.tax_rate
        )
        subtotal, tax_amount, total = _calculate_invoice_totals(
            items, resolved.rate, invoice.discount_amount
        )
        gst_hst, pst = _apply_split(subtotal, resolved)
        invoice.subtotal = subtotal
        invoice.tax_rate = resolved.rate
        invoice.tax_amount = tax_amount
        invoice.tax_gst_hst_amount = gst_hst
        invoice.tax_pst_amount = pst
        invoice.tax_rate_id = resolved.rate_id
        invoice.tax_rate_2_id = resolved.rate_2_id
        invoice.total = total

        for li in items:
            line = InvoiceLineItem(
                invoice_id=invoice.id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_rate=li.tax_rate if resolved.rate_id is None else resolved.rate,
                tax_rate_2=resolved.rate_2,
                tax_rate_id=resolved.rate_id,
                tax_rate_2_id=resolved.rate_2_id,
                total=_calculate_line_total(li),
            )
            db.add(line)

    await db.commit()
    await db.refresh(invoice)

    await log_activity(
        db,
        user_id=user.id,
        action="invoice_updated",
        resource_type="invoice",
        resource_id=str(invoice.id),
        details={"invoice_number": invoice.invoice_number, "total": invoice.total},
    )

    return invoice


async def delete_invoice(db: AsyncSession, invoice_id: uuid.UUID, user: User) -> None:
    invoice = await get_invoice(db, invoice_id, user)
    await db.delete(invoice)
    await db.commit()


async def send_invoice(db: AsyncSession, invoice_id: uuid.UUID, user: User) -> Invoice:
    invoice = await get_invoice(db, invoice_id, user)
    if invoice.status not in (InvoiceStatus.DRAFT,):
        raise ValidationError("Only draft invoices can be sent.")
    invoice.status = InvoiceStatus.SENT
    await db.commit()
    await db.refresh(invoice)

    from app.workflows.models import TriggerType
    from app.workflows.service import safe_dispatch

    await safe_dispatch(
        db,
        TriggerType.INVOICE_SENT,
        event_data={
            "invoice_number": invoice.invoice_number,
            "total": float(invoice.total),
        },
        contact_id=invoice.contact_id,
    )
    return invoice


async def record_payment(
    db: AsyncSession, invoice_id: uuid.UUID, data: InvoicePaymentCreate, user: User
) -> InvoicePayment:
    # Lock the invoice row to serialise concurrent payments
    result = await db.execute(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.payments))
        .with_for_update()
    )
    invoice = result.unique().scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice", str(invoice_id))
    # need_edit: taking money against a file that was shared with you read-only
    # is a write, not a read.
    await authorize_record(
        db,
        user,
        invoice.created_by,
        contact_id=invoice.contact_id,
        need_edit=True,
        resource_name="Invoice",
    )

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
    await db.flush()  # write payment so the DB sum includes it

    # Re-query actual total from DB to avoid stale ORM cache
    paid_result = await db.execute(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0))
        .where(InvoicePayment.invoice_id == invoice.id)
    )
    total_paid = Decimal(str(paid_result.scalar()))

    was_paid_transition = False
    if total_paid >= Decimal(str(invoice.total)):
        was_paid_transition = invoice.status != InvoiceStatus.PAID
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    await db.commit()
    await db.refresh(payment)

    await log_activity(
        db,
        user_id=user.id,
        action="payment_recorded",
        resource_type="invoice",
        resource_id=str(invoice.id),
        details={"payment_id": str(payment.id), "amount": payment.amount, "status": invoice.status.value},
    )

    # OBRAIN_EVENT_SPEC.md §3 — a manually-recorded payment against an
    # invoice. Uses the payment's own `date` (the moment it happened), not
    # "now" — the user may be backdating a payment recorded late.
    owner = await db.get(User, invoice.created_by)
    if owner is not None:
        await emit_event(
            db,
            event="payment_processed",
            org_id=resolve_org_id(owner),
            properties={"amountUSD": float(payment.amount), "source": "invoice"},
            timestamp=datetime.combine(payment.date, datetime.min.time(), tzinfo=timezone.utc),
        )

    # Auto-create income entry
    try:
        from app.income.service import create_income_from_payment
        await create_income_from_payment(db, invoice, payment, user)
    except ImportError:
        pass  # Income module not yet available

    # On a fresh PAID transition, send the contact a payment confirmation
    # email. Wrap broad — SMTP unconfigured, contact has no email, MX
    # bounce, etc., must NEVER fail the payment record. The DB write has
    # already committed at this point.
    if was_paid_transition:
        try:
            from app.email.service import send_payment_confirmation

            await send_payment_confirmation(db, invoice, payment, user)
        except Exception as exc:
            logger.warning(
                "invoicing.payment_confirmation_email_failed invoice_id=%s err=%s",
                invoice.id, str(exc)[:200],
            )

    from app.workflows.models import TriggerType
    from app.workflows.service import safe_dispatch

    await safe_dispatch(
        db,
        TriggerType.PAYMENT_RECEIVED,
        event_data={
            "invoice_number": invoice.invoice_number,
            "amount": float(payment.amount),
        },
        contact_id=invoice.contact_id,
    )
    if was_paid_transition:
        await safe_dispatch(
            db,
            TriggerType.INVOICE_PAID,
            event_data={
                "invoice_number": invoice.invoice_number,
                "total": float(invoice.total),
            },
            contact_id=invoice.contact_id,
        )

    return payment


async def get_invoice_stats(db: AsyncSession, user: User) -> dict:
    now = date.today()

    outstanding_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID])
    )
    outstanding_q = apply_visibility_filter(outstanding_q, Invoice.created_by, user, contact_col=Invoice.contact_id)
    total_outstanding = (await db.execute(outstanding_q)).scalar() or 0

    overdue_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    overdue_q = apply_visibility_filter(overdue_q, Invoice.created_by, user, contact_col=Invoice.contact_id)
    total_overdue = (await db.execute(overdue_q)).scalar() or 0

    paid_q = select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(
        func.extract("year", InvoicePayment.date) == now.year,
        func.extract("month", InvoicePayment.date) == now.month,
    )
    # Filter payments by joining to the invoice ownership
    paid_q = paid_q.join(Invoice, InvoicePayment.invoice_id == Invoice.id)
    paid_q = apply_visibility_filter(paid_q, Invoice.created_by, user, contact_col=Invoice.contact_id)
    total_paid = (await db.execute(paid_q)).scalar() or 0

    count_q = select(func.count(Invoice.id))
    count_q = apply_visibility_filter(count_q, Invoice.created_by, user, contact_col=Invoice.contact_id)
    invoice_count = (await db.execute(count_q)).scalar() or 0

    return {
        "total_outstanding": Decimal(str(total_outstanding)) if total_outstanding else Decimal('0'),
        "total_overdue": Decimal(str(total_overdue)) if total_overdue else Decimal('0'),
        "total_paid_this_month": Decimal(str(total_paid)) if total_paid else Decimal('0'),
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

        from app.workflows.models import TriggerType
        from app.workflows.service import safe_dispatch

        for inv in invoices:
            await safe_dispatch(
                db,
                TriggerType.INVOICE_OVERDUE,
                event_data={
                    "invoice_number": inv.invoice_number,
                    "total": float(inv.total),
                },
                contact_id=inv.contact_id,
            )
    return count
