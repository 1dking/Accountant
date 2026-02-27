from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError

from .models import SmsLog, SmsStatus


def _get_twilio_client(settings: Settings):
    from twilio.rest import Client

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValidationError("Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


# ---------------------------------------------------------------------------
# Core SMS sending
# ---------------------------------------------------------------------------


async def send_sms(
    db: AsyncSession,
    to: str,
    message: str,
    user: User,
    settings: Settings,
    related_invoice_id: uuid.UUID | None = None,
) -> SmsLog:
    """Send an SMS via Twilio and log it."""
    client = _get_twilio_client(settings)

    if not settings.twilio_from_number:
        raise ValidationError("No Twilio phone number configured. Set TWILIO_FROM_NUMBER.")

    try:
        twilio_message = client.messages.create(
            body=message,
            from_=settings.twilio_from_number,
            to=to,
        )
        status = SmsStatus.SENT
        sid = twilio_message.sid
    except Exception:
        status = SmsStatus.FAILED
        sid = None

    log = SmsLog(
        recipient=to,
        message=message[:1600],
        status=status,
        direction="outbound",
        related_invoice_id=related_invoice_id,
        twilio_sid=sid,
        created_by=user.id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Invoice-specific SMS
# ---------------------------------------------------------------------------


async def send_invoice_sms(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    to: str | None,
    user: User,
    settings: Settings,
) -> SmsLog:
    """Send an SMS with invoice summary and payment link."""
    from app.invoicing.models import Invoice

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    # Determine recipient phone number
    phone = to
    if not phone and hasattr(invoice, "contact") and invoice.contact:
        phone = getattr(invoice.contact, "phone", None)
    if not phone:
        raise ValidationError("No phone number provided or found on invoice contact")

    # Check for a Stripe payment link
    payment_url = ""
    try:
        from app.integrations.stripe.models import StripePaymentLink
        link_result = await db.execute(
            select(StripePaymentLink)
            .where(StripePaymentLink.invoice_id == invoice_id)
            .order_by(StripePaymentLink.created_at.desc())
        )
        link = link_result.scalar_one_or_none()
        if link and link.payment_url:
            payment_url = f"\nPay here: {link.payment_url}"
    except Exception:
        pass

    message = (
        f"Invoice {invoice.invoice_number}: ${invoice.total:.2f} {invoice.currency} "
        f"due {invoice.due_date}.{payment_url}"
    )

    return await send_sms(
        db, phone, message, user, settings,
        related_invoice_id=invoice.id,
    )


async def send_payment_reminder_sms(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    to: str | None,
    user: User,
    settings: Settings,
) -> SmsLog:
    """Send an overdue payment reminder via SMS."""
    from app.invoicing.models import Invoice
    from datetime import date, timezone

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    phone = to
    if not phone and hasattr(invoice, "contact") and invoice.contact:
        phone = getattr(invoice.contact, "phone", None)
    if not phone:
        raise ValidationError("No phone number provided or found on invoice contact")

    days_overdue = (date.today() - invoice.due_date).days if invoice.due_date else 0

    message = (
        f"Reminder: Invoice {invoice.invoice_number} for ${invoice.total:.2f} "
        f"is {days_overdue} day{'s' if days_overdue != 1 else ''} overdue. "
        f"Please arrange payment at your earliest convenience."
    )

    return await send_sms(
        db, phone, message, user, settings,
        related_invoice_id=invoice.id,
    )


async def send_payment_confirmation_sms(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    amount: float,
    to: str | None,
    user: User,
    settings: Settings,
) -> SmsLog:
    """Send a payment confirmation SMS."""
    from app.invoicing.models import Invoice

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    phone = to
    if not phone and hasattr(invoice, "contact") and invoice.contact:
        phone = getattr(invoice.contact, "phone", None)
    if not phone:
        raise ValidationError("No phone number provided or found on invoice contact")

    message = (
        f"Payment of ${amount:.2f} received for Invoice {invoice.invoice_number}. "
        f"Thank you!"
    )

    return await send_sms(
        db, phone, message, user, settings,
        related_invoice_id=invoice.id,
    )


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


async def list_sms_logs(
    db: AsyncSession, user_id: uuid.UUID
) -> list[SmsLog]:
    result = await db.execute(
        select(SmsLog)
        .where(SmsLog.created_by == user_id)
        .order_by(SmsLog.created_at.desc())
    )
    return list(result.scalars().all())
