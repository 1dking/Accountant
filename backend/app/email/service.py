
import uuid
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Sequence

import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError, ValidationError

from .models import SmtpConfig
from .schemas import SmtpConfigCreate, SmtpConfigUpdate

# ---------------------------------------------------------------------------
# Jinja2 template environment
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def render_template(template_name: str, **context: object) -> str:
    """Render a Jinja2 HTML email template with the given context."""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


# ---------------------------------------------------------------------------
# SMTP Config CRUD
# ---------------------------------------------------------------------------

async def create_smtp_config(
    db: AsyncSession,
    data: SmtpConfigCreate,
    user: User,
) -> SmtpConfig:
    encryption = get_encryption_service()
    encrypted_password = encryption.encrypt(data.password)

    # If this config should be the default, unset any existing defaults first.
    if data.is_default:
        await db.execute(
            update(SmtpConfig)
            .where(SmtpConfig.is_default.is_(True))
            .values(is_default=False)
        )

    config = SmtpConfig(
        id=uuid.uuid4(),
        name=data.name,
        host=data.host,
        port=data.port,
        username=data.username,
        encrypted_password=encrypted_password,
        from_email=data.from_email,
        from_name=data.from_name,
        use_tls=data.use_tls,
        is_default=data.is_default,
        created_by=user.id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def list_smtp_configs(
    db: AsyncSession,
    user: User,
) -> Sequence[SmtpConfig]:
    result = await db.execute(
        select(SmtpConfig)
        .order_by(SmtpConfig.created_at.desc())
    )
    return result.scalars().all()


async def get_smtp_config(
    db: AsyncSession,
    config_id: uuid.UUID,
) -> SmtpConfig:
    result = await db.execute(
        select(SmtpConfig).where(SmtpConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError(f"SMTP config {config_id} not found")
    return config


async def update_smtp_config(
    db: AsyncSession,
    config_id: uuid.UUID,
    data: SmtpConfigUpdate,
) -> SmtpConfig:
    config = await get_smtp_config(db, config_id)
    encryption = get_encryption_service()

    update_data = data.model_dump(exclude_unset=True)

    # Handle password encryption if a new password was provided.
    if "password" in update_data:
        raw_password = update_data.pop("password")
        config.encrypted_password = encryption.encrypt(raw_password)

    # If setting this config as default, unset other defaults first.
    if update_data.get("is_default"):
        await db.execute(
            update(SmtpConfig)
            .where(SmtpConfig.is_default.is_(True), SmtpConfig.id != config_id)
            .values(is_default=False)
        )

    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config


async def delete_smtp_config(
    db: AsyncSession,
    config_id: uuid.UUID,
) -> None:
    config = await get_smtp_config(db, config_id)
    await db.delete(config)
    await db.commit()


async def get_default_config(
    db: AsyncSession,
) -> SmtpConfig:
    result = await db.execute(
        select(SmtpConfig).where(SmtpConfig.is_default.is_(True))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError("No default SMTP configuration found")
    return config


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

async def send_email(
    smtp_config: SmtpConfig,
    to: str,
    subject: str,
    html_body: str,
    attachments: Optional[list[tuple[str, bytes, str]]] = None,
) -> None:
    """Send an email via SMTP.

    Parameters
    ----------
    smtp_config:
        The SMTP configuration to use.
    to:
        Recipient email address.
    subject:
        Email subject line.
    html_body:
        Rendered HTML content.
    attachments:
        Optional list of ``(filename, data_bytes, mime_type)`` tuples.
    """
    encryption = get_encryption_service()
    password = encryption.decrypt(smtp_config.encrypted_password)

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{smtp_config.from_name} <{smtp_config.from_email}>"
    msg["To"] = to
    msg["Subject"] = subject

    # HTML body
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Attachments
    if attachments:
        for filename, data_bytes, mime_type in attachments:
            maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
            part = MIMEApplication(data_bytes, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

    await aiosmtplib.send(
        msg,
        hostname=smtp_config.host,
        port=smtp_config.port,
        username=smtp_config.username,
        password=password,
        start_tls=smtp_config.use_tls,
    )


# ---------------------------------------------------------------------------
# High-level email workflows
# ---------------------------------------------------------------------------

async def send_invoice_email(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    smtp_config_id: Optional[uuid.UUID],
    recipient_email: Optional[str],
    subject: Optional[str],
    message: Optional[str],
    user: User,
) -> dict:
    """Load an invoice, render the template, generate a PDF, and send it."""
    from app.invoicing.models import Invoice
    from app.invoicing.pdf import generate_invoice_pdf

    # Resolve SMTP config
    if smtp_config_id:
        smtp_config = await get_smtp_config(db, smtp_config_id)
    else:
        smtp_config = await get_default_config(db)

    # Load invoice with its contact
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    # Determine recipient
    to_email = recipient_email or getattr(invoice, "contact_email", None)
    if not to_email:
        # Try to load from related contact
        if hasattr(invoice, "contact") and invoice.contact:
            to_email = invoice.contact.email
    if not to_email:
        raise ValidationError("No recipient email address provided or found on invoice contact")

    # Build subject
    email_subject = subject or f"Invoice {invoice.invoice_number}"

    # Render HTML
    now = datetime.now(timezone.utc)
    html_body = render_template(
        "invoice.html",
        invoice=invoice,
        custom_message=message,
        company_name=smtp_config.from_name,
        year=now.year,
    )

    # Fetch company branding for PDF
    from app.settings.service import get_company_settings

    company = await get_company_settings(db)
    pdf_kwargs: dict = {}
    if company:
        if company.company_name:
            pdf_kwargs["business_name"] = company.company_name
        addr_parts = []
        if company.address_line1:
            addr_parts.append(company.address_line1)
        city_state = ", ".join(filter(None, [company.city, company.state]))
        if city_state:
            if company.zip_code:
                city_state += f" {company.zip_code}"
            addr_parts.append(city_state)
        if company.country:
            addr_parts.append(company.country)
        if addr_parts:
            pdf_kwargs["company_address"] = ", ".join(addr_parts)
        if company.company_email:
            pdf_kwargs["company_email"] = company.company_email
        if company.company_phone:
            pdf_kwargs["company_phone"] = company.company_phone

    # Generate PDF attachment
    pdf_bytes = generate_invoice_pdf(invoice, **pdf_kwargs)
    attachments = [
        (f"Invoice-{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf"),
    ]

    await send_email(smtp_config, to_email, email_subject, html_body, attachments)

    return {"detail": f"Invoice email sent to {to_email}"}


async def send_payment_reminder(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    smtp_config_id: Optional[uuid.UUID],
    user: User,
) -> dict:
    """Load an invoice and send a payment reminder email."""
    from app.invoicing.models import Invoice

    # Resolve SMTP config
    if smtp_config_id:
        smtp_config = await get_smtp_config(db, smtp_config_id)
    else:
        smtp_config = await get_default_config(db)

    # Load invoice
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    # Determine recipient
    to_email: Optional[str] = getattr(invoice, "contact_email", None)
    if not to_email and hasattr(invoice, "contact") and invoice.contact:
        to_email = invoice.contact.email
    if not to_email:
        raise ValidationError("No recipient email address found on invoice contact")

    # Calculate days overdue
    now = datetime.now(timezone.utc).date()
    due_date = invoice.due_date if hasattr(invoice, "due_date") else None
    days_overdue = (now - due_date).days if due_date else 0

    # Render HTML
    html_body = render_template(
        "payment_reminder.html",
        invoice=invoice,
        days_overdue=days_overdue,
        company_name=smtp_config.from_name,
        year=datetime.now(timezone.utc).year,
    )

    email_subject = f"Payment Reminder: Invoice {invoice.invoice_number}"

    await send_email(smtp_config, to_email, email_subject, html_body)

    return {"detail": f"Payment reminder sent to {to_email}"}


async def send_estimate_email(
    db: AsyncSession,
    estimate_id: uuid.UUID,
    smtp_config_id: Optional[uuid.UUID],
    user: User,
) -> dict:
    """Load an estimate, generate PDF, create a public link, and send via email."""
    from app.estimates.models import Estimate, EstimateStatus
    from app.estimates.pdf import generate_estimate_pdf
    from app.public.models import ResourceType
    from app.public.service import create_public_token
    from sqlalchemy.orm import selectinload

    # Resolve SMTP config
    if smtp_config_id:
        smtp_config = await get_smtp_config(db, smtp_config_id)
    else:
        smtp_config = await get_default_config(db)

    # Load estimate with relationships
    result = await db.execute(
        select(Estimate)
        .options(selectinload(Estimate.contact), selectinload(Estimate.line_items))
        .where(Estimate.id == estimate_id)
    )
    estimate = result.scalar_one_or_none()
    if estimate is None:
        raise NotFoundError(f"Estimate {estimate_id} not found")

    # Determine recipient
    to_email: Optional[str] = None
    if estimate.contact:
        to_email = estimate.contact.email
    if not to_email:
        raise ValidationError("No recipient email address found on estimate contact")

    # Create a public access token for the "View Estimate" link
    pat = await create_public_token(db, ResourceType.ESTIMATE, estimate_id, user)
    from app.config import Settings
    settings = Settings()
    view_url = f"{settings.public_base_url}/p/{pat.token}"

    # Render HTML
    now = datetime.now(timezone.utc)
    html_body = render_template(
        "estimate.html",
        estimate=estimate,
        custom_message=None,
        company_name=smtp_config.from_name,
        view_url=view_url,
        year=now.year,
    )

    # Generate PDF attachment
    pdf_bytes = generate_estimate_pdf(estimate)
    attachments = [
        (f"Estimate-{estimate.estimate_number}.pdf", pdf_bytes, "application/pdf"),
    ]

    await send_email(smtp_config, to_email, f"Estimate {estimate.estimate_number}", html_body, attachments)

    # Mark as sent if still draft
    if estimate.status == EstimateStatus.DRAFT:
        estimate.status = EstimateStatus.SENT
        await db.commit()

    return {"detail": f"Estimate email sent to {to_email}"}
