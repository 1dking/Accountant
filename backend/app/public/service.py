import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError

from .models import PublicAccessToken, ResourceType


async def create_public_token(
    db: AsyncSession,
    resource_type: ResourceType,
    resource_id: uuid.UUID,
    user: User,
    expires_in_days: int | None = None,
) -> PublicAccessToken:
    """Create a new public access token for sharing a resource."""
    token = secrets.token_urlsafe(32)
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    public_token = PublicAccessToken(
        token=token,
        resource_type=resource_type,
        resource_id=resource_id,
        expires_at=expires_at,
        created_by=user.id,
    )
    db.add(public_token)
    await db.commit()
    await db.refresh(public_token)
    return public_token


async def get_token_by_value(db: AsyncSession, token: str) -> PublicAccessToken:
    """Look up an active, non-expired public access token by its string value."""
    result = await db.execute(
        select(PublicAccessToken).where(
            PublicAccessToken.token == token,
            PublicAccessToken.is_active.is_(True),
        )
    )
    pat = result.scalar_one_or_none()
    if pat is None:
        raise NotFoundError("PublicAccessToken", token)
    if pat.expires_at and pat.expires_at < datetime.now(timezone.utc):
        raise NotFoundError("PublicAccessToken", token)
    return pat


async def increment_view_count(db: AsyncSession, pat: PublicAccessToken) -> None:
    """Bump the view counter for a public token."""
    pat.view_count += 1
    await db.commit()


async def get_resource_data(db: AsyncSession, pat: PublicAccessToken) -> dict:
    """Load the actual estimate or invoice data for public viewing."""
    if pat.resource_type == ResourceType.ESTIMATE:
        from app.estimates.models import Estimate

        result = await db.execute(
            select(Estimate)
            .options(
                selectinload(Estimate.contact),
                selectinload(Estimate.line_items),
            )
            .where(Estimate.id == pat.resource_id)
        )
        estimate = result.scalar_one_or_none()
        if not estimate:
            raise NotFoundError("Estimate", str(pat.resource_id))
        return _serialize_estimate(estimate)

    elif pat.resource_type == ResourceType.INVOICE:
        from app.invoicing.models import Invoice

        result = await db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.contact),
                selectinload(Invoice.line_items),
                selectinload(Invoice.payments),
            )
            .where(Invoice.id == pat.resource_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice", str(pat.resource_id))
        return _serialize_invoice(invoice)

    raise ValidationError("Unknown resource type")


def _serialize_estimate(estimate) -> dict:  # type: ignore[no-untyped-def]
    """Serialize an Estimate ORM instance to a plain dict for public consumption."""
    return {
        "id": str(estimate.id),
        "type": "estimate",
        "number": estimate.estimate_number,
        "status": estimate.status.value,
        "issue_date": str(estimate.issue_date),
        "expiry_date": str(estimate.expiry_date),
        "subtotal": estimate.subtotal,
        "tax_rate": estimate.tax_rate,
        "tax_amount": estimate.tax_amount,
        "discount_amount": estimate.discount_amount,
        "total": estimate.total,
        "currency": estimate.currency,
        "notes": estimate.notes,
        "signed_by_name": getattr(estimate, "signed_by_name", None),
        "signed_at": (
            str(estimate.signed_at)
            if getattr(estimate, "signed_at", None)
            else None
        ),
        "contact": (
            {
                "company_name": estimate.contact.company_name if estimate.contact else None,
                "contact_name": estimate.contact.contact_name if estimate.contact else None,
                "email": estimate.contact.email if estimate.contact else None,
            }
            if estimate.contact
            else None
        ),
        "line_items": [
            {
                "description": li.description,
                "quantity": li.quantity,
                "unit_price": li.unit_price,
                "tax_rate": li.tax_rate,
                "total": li.total,
            }
            for li in estimate.line_items
        ],
    }


def _serialize_invoice(invoice) -> dict:  # type: ignore[no-untyped-def]
    """Serialize an Invoice ORM instance to a plain dict for public consumption."""
    return {
        "id": str(invoice.id),
        "type": "invoice",
        "number": invoice.invoice_number,
        "status": invoice.status.value,
        "issue_date": str(invoice.issue_date),
        "due_date": str(invoice.due_date),
        "subtotal": invoice.subtotal,
        "tax_rate": invoice.tax_rate,
        "tax_amount": invoice.tax_amount,
        "discount_amount": invoice.discount_amount,
        "total": invoice.total,
        "currency": invoice.currency,
        "notes": invoice.notes,
        "payment_terms": invoice.payment_terms,
        "contact": (
            {
                "company_name": invoice.contact.company_name if invoice.contact else None,
                "contact_name": invoice.contact.contact_name if invoice.contact else None,
                "email": invoice.contact.email if invoice.contact else None,
            }
            if invoice.contact
            else None
        ),
        "line_items": [
            {
                "description": li.description,
                "quantity": li.quantity,
                "unit_price": li.unit_price,
                "tax_rate": li.tax_rate,
                "total": li.total,
            }
            for li in invoice.line_items
        ],
        "payments": [
            {
                "amount": p.amount,
                "date": str(p.date),
                "payment_method": p.payment_method,
            }
            for p in (invoice.payments or [])
        ],
    }


async def get_company_branding(db: AsyncSession) -> dict | None:
    """Load company settings for public document display."""
    from app.settings.models import CompanySettings

    result = await db.execute(select(CompanySettings))
    settings = result.scalar_one_or_none()
    if not settings:
        return None
    return {
        "company_name": settings.company_name,
        "company_email": settings.company_email,
        "company_phone": settings.company_phone,
        "company_website": settings.company_website,
        "address_line1": settings.address_line1,
        "city": settings.city,
        "state": settings.state,
        "zip_code": settings.zip_code,
        "country": settings.country,
        "has_logo": bool(settings.logo_storage_path),
    }


async def accept_estimate(
    db: AsyncSession,
    pat: PublicAccessToken,
    signature_data: str,
    signer_name: str,
    signer_ip: str,
) -> dict:
    """Accept an estimate with a digital signature via a public link."""
    from app.estimates.models import Estimate, EstimateStatus

    if pat.resource_type != ResourceType.ESTIMATE:
        raise ValidationError("Can only accept estimates")

    result = await db.execute(
        select(Estimate).where(Estimate.id == pat.resource_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise NotFoundError("Estimate", str(pat.resource_id))
    if estimate.status not in (EstimateStatus.DRAFT, EstimateStatus.SENT):
        raise ValidationError(
            f"Cannot accept estimate with status: {estimate.status.value}"
        )

    estimate.status = EstimateStatus.ACCEPTED
    estimate.signature_data = signature_data
    estimate.signed_by_name = signer_name
    estimate.signed_at = datetime.now(timezone.utc)
    estimate.signer_ip = signer_ip
    await db.commit()

    return {"status": "accepted", "signed_at": str(estimate.signed_at)}


async def revoke_token(
    db: AsyncSession, token_id: uuid.UUID, user: User
) -> None:
    """Deactivate a public access token."""
    result = await db.execute(
        select(PublicAccessToken).where(
            PublicAccessToken.id == token_id,
        )
    )
    pat = result.scalar_one_or_none()
    if not pat:
        raise NotFoundError("PublicAccessToken", str(token_id))
    pat.is_active = False
    await db.commit()


async def list_tokens_for_resource(
    db: AsyncSession,
    resource_type: ResourceType,
    resource_id: uuid.UUID,
) -> list[PublicAccessToken]:
    """Return all active tokens for a given resource."""
    result = await db.execute(
        select(PublicAccessToken)
        .where(
            PublicAccessToken.resource_type == resource_type,
            PublicAccessToken.resource_id == resource_id,
            PublicAccessToken.is_active.is_(True),
        )
        .order_by(PublicAccessToken.created_at.desc())
    )
    return list(result.scalars().all())


async def create_public_payment_intent(
    db: AsyncSession,
    pat: PublicAccessToken,
    settings,
) -> dict:
    """Create a Stripe PaymentIntent for an invoice accessed via public token."""
    import stripe as stripe_lib

    from app.integrations.stripe.models import PaymentLinkStatus, StripePaymentLink
    from app.invoicing.models import Invoice, InvoiceStatus

    if pat.resource_type != ResourceType.INVOICE:
        raise ValidationError("Can only pay invoices")

    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    stripe_lib.api_key = settings.stripe_secret_key

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.payments))
        .where(Invoice.id == pat.resource_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice", str(pat.resource_id))

    payable_statuses = {
        InvoiceStatus.SENT,
        InvoiceStatus.VIEWED,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.PARTIALLY_PAID,
    }
    if invoice.status not in payable_statuses:
        raise ValidationError(
            f"Invoice status '{invoice.status.value}' is not payable"
        )

    total_paid = sum(p.amount for p in (invoice.payments or []))
    balance_due = invoice.total - total_paid
    if balance_due <= 0:
        raise ValidationError("Invoice is already fully paid")

    # Reuse existing pending PaymentIntent if one exists (idempotency)
    existing = await db.execute(
        select(StripePaymentLink).where(
            StripePaymentLink.invoice_id == invoice.id,
            StripePaymentLink.status == PaymentLinkStatus.PENDING,
            StripePaymentLink.payment_intent_id.isnot(None),
        ).order_by(StripePaymentLink.created_at.desc())
    )
    existing_link = existing.scalar_one_or_none()
    if existing_link and existing_link.payment_intent_id:
        try:
            pi = stripe_lib.PaymentIntent.retrieve(existing_link.payment_intent_id)
            if pi.status in (
                "requires_payment_method",
                "requires_confirmation",
                "requires_action",
            ):
                return {
                    "client_secret": pi.client_secret,
                    "publishable_key": settings.stripe_publishable_key,
                    "amount": pi.amount,
                    "currency": invoice.currency,
                }
        except stripe_lib.error.StripeError:
            pass  # Fall through to create a new one

    amount_cents = int(round(balance_due * 100))

    payment_intent = stripe_lib.PaymentIntent.create(
        amount=amount_cents,
        currency=invoice.currency.lower(),
        metadata={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
        },
        automatic_payment_methods={"enabled": True},
        description=f"Payment for Invoice {invoice.invoice_number}",
    )

    payment_link = StripePaymentLink(
        invoice_id=invoice.id,
        payment_intent_id=payment_intent.id,
        amount=balance_due,
        currency=invoice.currency,
        status=PaymentLinkStatus.PENDING,
        created_by=invoice.created_by,
    )
    db.add(payment_link)
    await db.commit()

    return {
        "client_secret": payment_intent.client_secret,
        "publishable_key": settings.stripe_publishable_key,
        "amount": amount_cents,
        "currency": invoice.currency,
    }
