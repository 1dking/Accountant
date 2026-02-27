
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.contacts.models import Contact
from app.core.exceptions import NotFoundError, ValidationError
from app.invoicing.models import Invoice, InvoiceStatus
from app.invoicing.reminder_models import (
    PaymentReminder,
    ReminderChannel,
    ReminderRule,
    ReminderStatus,
)
from app.invoicing.reminder_schemas import (
    ManualReminderRequest,
    ReminderRuleCreate,
    ReminderRuleUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reminder Rule CRUD
# ---------------------------------------------------------------------------


async def list_reminder_rules(db: AsyncSession) -> Sequence[ReminderRule]:
    result = await db.execute(
        select(ReminderRule).order_by(ReminderRule.days_offset.asc())
    )
    return result.scalars().all()


async def get_reminder_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> ReminderRule:
    result = await db.execute(
        select(ReminderRule).where(ReminderRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundError(f"Reminder rule {rule_id} not found")
    return rule


async def create_reminder_rule(
    db: AsyncSession,
    data: ReminderRuleCreate,
    user: User,
) -> ReminderRule:
    _validate_rule_templates(data.channel, data.email_subject, data.email_body, data.sms_body)

    rule = ReminderRule(
        id=uuid.uuid4(),
        name=data.name,
        days_offset=data.days_offset,
        channel=data.channel,
        email_subject=data.email_subject,
        email_body=data.email_body,
        sms_body=data.sms_body,
        is_active=data.is_active,
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_reminder_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
    data: ReminderRuleUpdate,
) -> ReminderRule:
    rule = await get_reminder_rule(db, rule_id)
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(rule, field, value)

    # Validate that templates are consistent with channel after update
    _validate_rule_templates(rule.channel, rule.email_subject, rule.email_body, rule.sms_body)

    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_reminder_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> None:
    rule = await get_reminder_rule(db, rule_id)
    await db.delete(rule)
    await db.commit()


# ---------------------------------------------------------------------------
# Reminder history
# ---------------------------------------------------------------------------


async def get_reminder_history(
    db: AsyncSession,
    invoice_id: uuid.UUID,
) -> Sequence[PaymentReminder]:
    result = await db.execute(
        select(PaymentReminder)
        .where(PaymentReminder.invoice_id == invoice_id)
        .order_by(PaymentReminder.created_at.desc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Manual send
# ---------------------------------------------------------------------------


async def send_manual_reminder(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    data: ManualReminderRequest,
    user: User,
    settings: Settings,
) -> PaymentReminder:
    """Send a one-off reminder for a specific invoice."""

    # Load the invoice
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    # Load the contact
    result = await db.execute(
        select(Contact).where(Contact.id == invoice.contact_id)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise NotFoundError(f"Contact for invoice {invoice_id} not found")

    # Determine subject/body defaults
    email_subject = data.email_subject or f"Payment Reminder: Invoice {invoice.invoice_number}"
    email_body = data.email_body or _default_email_body(invoice, contact)
    sms_body = data.sms_body or _default_sms_body(invoice)

    # Send
    reminder = await _send_reminder(
        db=db,
        invoice=invoice,
        contact=contact,
        channel=data.channel,
        reminder_type="manual",
        rule_id=None,
        email_subject=email_subject,
        email_body=email_body,
        sms_body=sms_body,
        user=user,
        settings=settings,
    )
    return reminder


# ---------------------------------------------------------------------------
# Daily job: process all active reminder rules
# ---------------------------------------------------------------------------


async def process_reminders(
    db: AsyncSession,
    settings: Settings,
) -> int:
    """Process all active reminder rules against unpaid invoices.

    Called by the daily scheduler job. Returns the number of reminders sent.
    """
    today = date.today()
    sent_count = 0

    # Load active rules
    rules_result = await db.execute(
        select(ReminderRule).where(ReminderRule.is_active.is_(True))
    )
    rules = list(rules_result.scalars().all())

    if not rules:
        return 0

    # Load invoices that are eligible for reminders:
    # sent, viewed, overdue, or partially_paid (i.e. not paid, not draft, not cancelled)
    eligible_statuses = [
        InvoiceStatus.SENT,
        InvoiceStatus.VIEWED,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.PARTIALLY_PAID,
    ]
    invoices_result = await db.execute(
        select(Invoice).where(Invoice.status.in_(eligible_statuses))
    )
    invoices = list(invoices_result.scalars().all())

    if not invoices:
        return 0

    # Load a system user for sending (first admin)
    from app.auth.models import Role
    user_result = await db.execute(
        select(User).where(User.role == Role.ADMIN).limit(1)
    )
    system_user = user_result.scalar_one_or_none()
    if system_user is None:
        logger.warning("No admin user found to send reminders")
        return 0

    for invoice in invoices:
        if not invoice.due_date:
            continue

        # Load contact
        contact_result = await db.execute(
            select(Contact).where(Contact.id == invoice.contact_id)
        )
        contact = contact_result.scalar_one_or_none()
        if contact is None:
            continue

        for rule in rules:
            # Calculate the target date for this rule
            # days_offset < 0: send X days before due
            # days_offset == 0: send on due date
            # days_offset > 0: send X days after due
            target_date = invoice.due_date
            days_diff = (today - target_date).days  # positive = after due date

            # We should send this reminder if today matches the rule's offset
            if days_diff != rule.days_offset:
                continue

            # Check if we already sent this reminder for this invoice + rule combo
            existing = await db.execute(
                select(PaymentReminder).where(
                    and_(
                        PaymentReminder.invoice_id == invoice.id,
                        PaymentReminder.reminder_rule_id == rule.id,
                        PaymentReminder.status == ReminderStatus.SENT,
                    )
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            # Determine type label
            if rule.days_offset < 0:
                reminder_type = "before_due"
            elif rule.days_offset == 0:
                reminder_type = "on_due"
            else:
                reminder_type = "after_due"

            # Build default templates if not provided on the rule
            email_subject = rule.email_subject or f"Payment Reminder: Invoice {invoice.invoice_number}"
            email_body = rule.email_body or _default_email_body(invoice, contact)
            sms_body = rule.sms_body or _default_sms_body(invoice)

            # Apply template variables
            email_subject = _apply_template_vars(email_subject, invoice, contact)
            email_body = _apply_template_vars(email_body, invoice, contact)
            sms_body = _apply_template_vars(sms_body, invoice, contact)

            try:
                await _send_reminder(
                    db=db,
                    invoice=invoice,
                    contact=contact,
                    channel=rule.channel,
                    reminder_type=reminder_type,
                    rule_id=rule.id,
                    email_subject=email_subject,
                    email_body=email_body,
                    sms_body=sms_body,
                    user=system_user,
                    settings=settings,
                )
                sent_count += 1
            except Exception:
                logger.exception(
                    "Failed to send reminder for invoice %s rule %s",
                    invoice.id, rule.id,
                )

    return sent_count


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_rule_templates(
    channel: ReminderChannel,
    email_subject: Optional[str],
    email_body: Optional[str],
    sms_body: Optional[str],
) -> None:
    """Ensure the rule has appropriate templates for its channel."""
    # We allow empty templates because defaults will be used at send time.
    # But if channel is SMS-only and no sms_body is provided, that's still ok
    # because we have a default. No strict validation needed here.
    pass


async def _send_reminder(
    db: AsyncSession,
    invoice: Invoice,
    contact: Contact,
    channel: ReminderChannel,
    reminder_type: str,
    rule_id: Optional[uuid.UUID],
    email_subject: str,
    email_body: str,
    sms_body: str,
    user: User,
    settings: Settings,
) -> PaymentReminder:
    """Send a reminder via the specified channel(s) and record the result."""
    now = datetime.now(timezone.utc)
    error_messages: list[str] = []
    any_success = False

    # Send email
    if channel in (ReminderChannel.EMAIL, ReminderChannel.BOTH):
        if contact.email:
            try:
                await _send_reminder_email(db, contact.email, email_subject, email_body)
                any_success = True
            except Exception as exc:
                logger.exception("Email reminder failed for invoice %s", invoice.id)
                error_messages.append(f"Email failed: {exc}")
        else:
            error_messages.append("No email address on contact")

    # Send SMS
    if channel in (ReminderChannel.SMS, ReminderChannel.BOTH):
        if contact.phone:
            try:
                await _send_reminder_sms(db, contact.phone, sms_body, user, settings, invoice.id)
                any_success = True
            except Exception as exc:
                logger.exception("SMS reminder failed for invoice %s", invoice.id)
                error_messages.append(f"SMS failed: {exc}")
        else:
            error_messages.append("No phone number on contact")

    # Determine overall status
    if any_success:
        status = ReminderStatus.SENT
    elif error_messages:
        status = ReminderStatus.FAILED
    else:
        status = ReminderStatus.SKIPPED

    reminder = PaymentReminder(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        contact_id=contact.id,
        reminder_rule_id=rule_id,
        reminder_type=reminder_type,
        channel=channel,
        status=status,
        sent_at=now if any_success else None,
        error_message="; ".join(error_messages) if error_messages else None,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def _send_reminder_email(
    db: AsyncSession,
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    """Send a reminder email using the default SMTP config."""
    from app.email.service import get_default_config, send_email

    smtp_config = await get_default_config(db)
    await send_email(smtp_config, to_email, subject, html_body)


async def _send_reminder_sms(
    db: AsyncSession,
    to_phone: str,
    message: str,
    user: User,
    settings: Settings,
    invoice_id: uuid.UUID,
) -> None:
    """Send a reminder SMS via Twilio."""
    from app.integrations.twilio.service import send_sms

    await send_sms(
        db=db,
        to=to_phone,
        message=message,
        user=user,
        settings=settings,
        related_invoice_id=invoice_id,
    )


def _default_email_body(invoice: Invoice, contact: Contact) -> str:
    """Generate a default HTML email body for a payment reminder."""
    contact_name = contact.contact_name or contact.company_name
    days_info = ""
    if invoice.due_date:
        days = (date.today() - invoice.due_date).days
        if days > 0:
            days_info = f"<p>This invoice is <strong>{days} day{'s' if days != 1 else ''} overdue</strong>.</p>"
        elif days == 0:
            days_info = "<p>This invoice is <strong>due today</strong>.</p>"
        else:
            days_info = f"<p>This invoice is due in <strong>{abs(days)} day{'s' if abs(days) != 1 else ''}</strong>.</p>"

    return (
        f"<html><body>"
        f"<p>Dear {contact_name},</p>"
        f"<p>This is a friendly reminder regarding Invoice <strong>{invoice.invoice_number}</strong> "
        f"for <strong>${invoice.total:.2f} {invoice.currency}</strong>, "
        f"due on <strong>{invoice.due_date}</strong>.</p>"
        f"{days_info}"
        f"<p>Please arrange payment at your earliest convenience.</p>"
        f"<p>Thank you for your business.</p>"
        f"</body></html>"
    )


def _default_sms_body(invoice: Invoice) -> str:
    """Generate a default SMS body for a payment reminder."""
    days = (date.today() - invoice.due_date).days if invoice.due_date else 0
    if days > 0:
        timing = f"{days} day{'s' if days != 1 else ''} overdue"
    elif days == 0:
        timing = "due today"
    else:
        timing = f"due in {abs(days)} day{'s' if abs(days) != 1 else ''}"

    return (
        f"Reminder: Invoice {invoice.invoice_number} for ${invoice.total:.2f} "
        f"is {timing}. Please arrange payment at your earliest convenience."
    )


def _apply_template_vars(template: str, invoice: Invoice, contact: Contact) -> str:
    """Replace template placeholders with actual values."""
    replacements = {
        "{{invoice_number}}": invoice.invoice_number,
        "{{total}}": f"${invoice.total:.2f}",
        "{{currency}}": invoice.currency,
        "{{due_date}}": str(invoice.due_date) if invoice.due_date else "",
        "{{contact_name}}": contact.contact_name or contact.company_name,
        "{{company_name}}": contact.company_name,
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
