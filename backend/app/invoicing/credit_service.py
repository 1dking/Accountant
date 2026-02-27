"""Business logic for credit notes and refunds."""


import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.invoicing.credit_models import CreditNote, CreditNoteStatus
from app.invoicing.models import Invoice, InvoicePayment, InvoiceStatus


async def generate_credit_note_number(db: AsyncSession) -> str:
    """Generate the next sequential credit note number."""
    result = await db.execute(select(func.count(CreditNote.id)))
    count = (result.scalar() or 0) + 1
    return f"CN-{count:04d}"


async def list_credit_notes(
    db: AsyncSession,
    invoice_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
) -> list[CreditNote]:
    """List credit notes, optionally filtered by invoice or contact."""
    query = select(CreditNote).order_by(CreditNote.created_at.desc())

    if invoice_id is not None:
        query = query.where(CreditNote.invoice_id == invoice_id)
    if contact_id is not None:
        query = query.where(CreditNote.contact_id == contact_id)

    result = await db.execute(query)
    return list(result.scalars().all())


async def create_credit_note(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    amount: float,
    issue_date: date,
    user: User,
    reason: str | None = None,
) -> CreditNote:
    """Create a credit note against an existing invoice."""
    # Validate invoice exists
    invoice_result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = invoice_result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice", str(invoice_id))

    # Validate amount does not exceed invoice total
    existing_credits_result = await db.execute(
        select(func.coalesce(func.sum(CreditNote.amount), 0)).where(
            CreditNote.invoice_id == invoice_id,
            CreditNote.status != CreditNoteStatus.DRAFT,
        )
    )
    existing_credit_total = float(existing_credits_result.scalar() or 0)

    if amount + existing_credit_total > invoice.total:
        raise ValidationError(
            f"Credit note amount ({amount}) plus existing credits "
            f"({existing_credit_total}) exceeds invoice total ({invoice.total})."
        )

    credit_note_number = await generate_credit_note_number(db)

    credit_note = CreditNote(
        credit_note_number=credit_note_number,
        invoice_id=invoice_id,
        contact_id=invoice.contact_id,
        amount=amount,
        reason=reason,
        status=CreditNoteStatus.DRAFT,
        issue_date=issue_date,
        created_by=user.id,
    )
    db.add(credit_note)
    await db.commit()
    await db.refresh(credit_note)
    return credit_note


async def get_credit_note(
    db: AsyncSession, credit_note_id: uuid.UUID
) -> CreditNote:
    """Get a single credit note by ID."""
    result = await db.execute(
        select(CreditNote).where(CreditNote.id == credit_note_id)
    )
    credit_note = result.scalar_one_or_none()
    if credit_note is None:
        raise NotFoundError("CreditNote", str(credit_note_id))
    return credit_note


async def apply_credit_note(
    db: AsyncSession,
    credit_note_id: uuid.UUID,
    user: User,
) -> CreditNote:
    """Apply a credit note, reducing the invoice balance.

    When applied, a negative payment record is added to the invoice to reflect
    the credit, and the invoice status is updated accordingly.
    """
    credit_note = await get_credit_note(db, credit_note_id)

    if credit_note.status == CreditNoteStatus.APPLIED:
        raise ValidationError("This credit note has already been applied.")
    if credit_note.status == CreditNoteStatus.DRAFT:
        # Auto-issue before applying
        credit_note.status = CreditNoteStatus.ISSUED

    # Load the invoice
    invoice_result = await db.execute(
        select(Invoice).where(Invoice.id == credit_note.invoice_id)
    )
    invoice = invoice_result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice", str(credit_note.invoice_id))

    # Record a payment-like entry for the credit note
    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=credit_note.amount,
        date=credit_note.issue_date,
        payment_method="credit_note",
        reference=credit_note.credit_note_number,
        notes=f"Credit note applied: {credit_note.reason or 'N/A'}",
        recorded_by=user.id,
    )
    db.add(payment)

    # Update credit note status
    credit_note.status = CreditNoteStatus.APPLIED
    credit_note.applied_at = datetime.now(timezone.utc)

    # Recalculate invoice balance and update status
    payments_result = await db.execute(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(
            InvoicePayment.invoice_id == invoice.id
        )
    )
    total_paid = float(payments_result.scalar() or 0) + credit_note.amount

    if total_paid >= invoice.total:
        invoice.status = InvoiceStatus.PAID
    elif total_paid > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    await db.commit()
    await db.refresh(credit_note)
    return credit_note


async def get_contact_credit_balance(
    db: AsyncSession, contact_id: uuid.UUID
) -> dict:
    """Get the credit balance summary for a contact."""
    # Total issued (issued + applied)
    issued_result = await db.execute(
        select(func.coalesce(func.sum(CreditNote.amount), 0)).where(
            CreditNote.contact_id == contact_id,
            CreditNote.status.in_([
                CreditNoteStatus.ISSUED,
                CreditNoteStatus.APPLIED,
            ]),
        )
    )
    total_issued = float(issued_result.scalar() or 0)

    # Total applied
    applied_result = await db.execute(
        select(func.coalesce(func.sum(CreditNote.amount), 0)).where(
            CreditNote.contact_id == contact_id,
            CreditNote.status == CreditNoteStatus.APPLIED,
        )
    )
    total_applied = float(applied_result.scalar() or 0)

    return {
        "contact_id": contact_id,
        "total_issued": total_issued,
        "total_applied": total_applied,
        "available_balance": round(total_issued - total_applied, 2),
    }
