
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import stripe as stripe_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.events.service import emit_event, resolve_org_id

from .models import (
    PaymentLinkStatus,
    StripePaymentLink,
    StripeSubscription,
    SubscriptionInterval,
    SubscriptionStatus,
)
from .schemas import CreateSubscriptionRequest

logger = logging.getLogger(__name__)


def _configure_stripe(settings: Settings) -> None:
    stripe_lib.api_key = settings.stripe_secret_key


# ---------------------------------------------------------------------------
# One-time payment via Checkout
# ---------------------------------------------------------------------------


async def create_checkout_session(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user: User,
    settings: Settings,
    base_url: str = "",
) -> StripePaymentLink:
    """Create a Stripe Checkout Session for an invoice."""
    from app.invoicing.models import Invoice

    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    _configure_stripe(settings)

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    from app.integrations.stripe_connect.service import get_active_connect_account_id

    connect_account_id = await get_active_connect_account_id(db, invoice.created_by)

    amount_cents = int(Decimal(str(invoice.total)) * Decimal('100'))

    # Use the request origin so URLs work in both dev and production
    origin = base_url.rstrip("/") if base_url else "http://localhost:5173"

    session_kwargs = dict(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": invoice.currency.lower(),
                    "product_data": {
                        "name": f"Invoice {invoice.invoice_number}",
                        "description": f"Payment for invoice {invoice.invoice_number}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{origin}/invoices?payment=success",
        cancel_url=f"{origin}/invoices?payment=cancelled",
        metadata={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
        },
    )
    if connect_account_id:
        session_kwargs["stripe_account"] = connect_account_id
    session = stripe_lib.checkout.Session.create(**session_kwargs)

    payment_link = StripePaymentLink(
        invoice_id=invoice.id,
        checkout_session_id=session.id,
        payment_url=session.url,
        amount=invoice.total,
        currency=invoice.currency,
        status=PaymentLinkStatus.PENDING,
        created_by=user.id,
    )
    db.add(payment_link)
    await db.commit()
    await db.refresh(payment_link)
    return payment_link


async def get_payment_link(
    db: AsyncSession, invoice_id: uuid.UUID
) -> StripePaymentLink | None:
    result = await db.execute(
        select(StripePaymentLink)
        .where(StripePaymentLink.invoice_id == invoice_id)
        .order_by(StripePaymentLink.created_at.desc())
    )
    return result.scalars().first()


async def ensure_payment_url(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user: User,
    settings: Settings,
    base_url: str = "",
) -> str | None:
    """Return a payable Stripe URL for an invoice, creating one if needed.

    Returns None — rather than raising — when Stripe isn't configured or the
    call to Stripe fails. Callers use this to decide whether to render a
    "Pay Now" button, and a payment provider being down must not block the
    invoice email itself from going out.

    Reuses an existing PENDING link instead of minting a session per send, so
    resending an invoice doesn't litter Stripe with duplicate checkouts.
    """
    if not settings.stripe_secret_key:
        return None

    existing = await get_payment_link(db, invoice_id)
    if existing and existing.status == PaymentLinkStatus.PENDING and existing.payment_url:
        return existing.payment_url

    try:
        link = await create_checkout_session(db, invoice_id, user, settings, base_url)
    except Exception:  # noqa: BLE001 — never let Stripe break the send
        logger.exception("Could not create Stripe payment link for invoice %s", invoice_id)
        return None

    return link.payment_url


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


async def create_subscription(
    db: AsyncSession,
    data: CreateSubscriptionRequest,
    user: User,
    settings: Settings,
) -> StripeSubscription:
    """Create a Stripe Customer + Subscription for recurring billing."""
    from app.contacts.models import Contact

    _configure_stripe(settings)

    result = await db.execute(select(Contact).where(Contact.id == data.contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise NotFoundError(f"Contact {data.contact_id} not found")

    # Create or reuse Stripe Customer
    customer = stripe_lib.Customer.create(
        name=contact.name,
        email=getattr(contact, "email", None),
        metadata={"contact_id": str(contact.id)},
    )

    interval_map = {
        "monthly": "month",
        "quarterly": "month",
        "yearly": "year",
    }
    interval_count_map = {
        "monthly": 1,
        "quarterly": 3,
        "yearly": 1,
    }

    stripe_interval = interval_map.get(data.interval, "month")
    stripe_interval_count = interval_count_map.get(data.interval, 1)
    amount_cents = int(Decimal(str(data.amount)) * Decimal('100'))

    # Create Price + Subscription
    price = stripe_lib.Price.create(
        unit_amount=amount_cents,
        currency=data.currency.lower(),
        recurring={
            "interval": stripe_interval,
            "interval_count": stripe_interval_count,
        },
        product_data={"name": data.name},
    )

    subscription = stripe_lib.Subscription.create(
        customer=customer.id,
        items=[{"price": price.id}],
        metadata={
            "contact_id": str(contact.id),
            "name": data.name,
        },
    )

    period_end = None
    if subscription.current_period_end:
        period_end = datetime.fromtimestamp(
            subscription.current_period_end, tz=timezone.utc
        )

    sub = StripeSubscription(
        contact_id=contact.id,
        stripe_subscription_id=subscription.id,
        stripe_customer_id=customer.id,
        name=data.name,
        amount=data.amount,
        currency=data.currency,
        interval=SubscriptionInterval(data.interval),
        status=SubscriptionStatus.ACTIVE,
        current_period_end=period_end,
        created_by=user.id,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def list_subscriptions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[StripeSubscription]:
    result = await db.execute(
        select(StripeSubscription)
        .where(StripeSubscription.created_by == user_id)
        .order_by(StripeSubscription.created_at.desc())
    )
    return list(result.scalars().all())


async def cancel_subscription(
    db: AsyncSession,
    sub_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> StripeSubscription:
    """Cancel a Stripe subscription."""
    _configure_stripe(settings)

    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.id == sub_id,
            StripeSubscription.created_by == user.id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise NotFoundError("Subscription not found")

    stripe_lib.Subscription.cancel(sub.stripe_subscription_id)

    sub.status = SubscriptionStatus.CANCELLED
    await db.commit()
    await db.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------


async def handle_webhook_event(
    db: AsyncSession,
    payload: bytes,
    sig_header: str,
    settings: Settings,
) -> dict:
    """Process incoming Stripe webhook events."""
    _configure_stripe(settings)

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe_lib.error.SignatureVerificationError:
        raise ValidationError("Invalid webhook signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data_object)
    elif event_type == "payment_intent.succeeded":
        await _handle_payment_intent_succeeded(db, data_object)
    elif event_type == "invoice.payment_succeeded":
        await _handle_subscription_payment(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_cancelled(db, data_object)

    return {"event_type": event_type, "handled": True}


async def _connect_account_mismatch(
    db: AsyncSession, owner_id: uuid.UUID, expected_connect_account_id: str | None
) -> bool:
    """True if this event's connected account doesn't match the record owner's.

    expected_connect_account_id is only set when this event arrived through
    the Connect-scoped webhook (app.integrations.stripe_connect). The
    platform's own webhook always passes None here, which skips this check
    entirely — existing single-tenant behavior is untouched.
    """
    if expected_connect_account_id is None:
        return False

    from app.integrations.stripe_connect.service import get_connect_account_for_user

    owner_account = await get_connect_account_for_user(db, owner_id)
    if owner_account is None or owner_account.stripe_account_id != expected_connect_account_id:
        logger.warning(
            "stripe_connect webhook account mismatch: event acct=%s owner acct=%s",
            expected_connect_account_id,
            getattr(owner_account, "stripe_account_id", None),
        )
        return True
    return False


async def _handle_checkout_completed(
    db: AsyncSession, session: dict, expected_connect_account_id: str | None = None
) -> None:
    """When a checkout session completes, mark the invoice as paid."""
    session_id = session.get("id")
    invoice_id_str = session.get("metadata", {}).get("invoice_id")

    if not session_id:
        return

    # Update payment link status
    result = await db.execute(
        select(StripePaymentLink).where(
            StripePaymentLink.checkout_session_id == session_id
        )
    )
    payment_link = result.scalar_one_or_none()
    if payment_link:
        payment_link.status = PaymentLinkStatus.COMPLETED
        payment_link.payment_intent_id = session.get("payment_intent")
        payment_link.paid_at = datetime.now(timezone.utc)

    # Record the payment on the invoice
    if invoice_id_str:
        from app.invoicing.models import Invoice, InvoicePayment, InvoiceStatus
        from datetime import date as date_type

        invoice_uuid = uuid.UUID(invoice_id_str)
        inv_result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_uuid)
        )
        invoice = inv_result.scalar_one_or_none()
        if invoice and await _connect_account_mismatch(db, invoice.created_by, expected_connect_account_id):
            return
        if invoice:
            payment = InvoicePayment(
                invoice_id=invoice.id,
                amount=Decimal(str(session.get("amount_total", 0))) / Decimal('100'),
                date=date_type.today(),
                payment_method="stripe",
                reference=session.get("payment_intent"),
                recorded_by=invoice.created_by,
            )
            db.add(payment)
            invoice.status = InvoiceStatus.PAID

            # Also create an income record
            from app.income.models import Income, IncomeCategory

            income = Income(
                contact_id=invoice.contact_id,
                invoice_id=invoice.id,
                category=IncomeCategory.INVOICE_PAYMENT,
                description=f"Stripe payment for Invoice {invoice.invoice_number}",
                amount=Decimal(str(session.get("amount_total", 0))) / Decimal('100'),
                currency=invoice.currency,
                date=date_type.today(),
                payment_method="stripe",
                reference=session.get("payment_intent"),
                created_by=invoice.created_by,
            )
            db.add(income)

            # OBRAIN_EVENT_SPEC.md §3 — Stripe Checkout paid an invoice.
            owner = await db.get(User, invoice.created_by)
            if owner is not None:
                await emit_event(
                    db,
                    event="payment_processed",
                    org_id=resolve_org_id(owner),
                    properties={"amountUSD": float(payment.amount), "source": "invoice"},
                )

    # Handle proposal payments
    proposal_id_str = session.get("metadata", {}).get("proposal_id")
    if proposal_id_str:
        from app.proposals.service import handle_proposal_payment_webhook
        await handle_proposal_payment_webhook(
            db,
            proposal_id_str=proposal_id_str,
            payment_intent_id=session.get("payment_intent"),
            expected_connect_account_id=expected_connect_account_id,
        )

    await db.commit()


async def _handle_payment_intent_succeeded(
    db: AsyncSession, payment_intent: dict, expected_connect_account_id: str | None = None
) -> None:
    """When a PaymentIntent succeeds (embedded payment), mark the invoice as paid."""
    from datetime import date as date_type

    from sqlalchemy.orm import selectinload

    from app.invoicing.models import Invoice, InvoicePayment, InvoiceStatus

    pi_id = payment_intent.get("id")
    invoice_id_str = payment_intent.get("metadata", {}).get("invoice_id")

    if not pi_id:
        return

    # Skip if this PaymentIntent came from a Checkout Session (handled separately)
    result = await db.execute(
        select(StripePaymentLink).where(
            StripePaymentLink.checkout_session_id.isnot(None),
            StripePaymentLink.payment_intent_id == pi_id,
        )
    )
    if result.scalar_one_or_none():
        return

    # Update payment link status
    result = await db.execute(
        select(StripePaymentLink).where(
            StripePaymentLink.payment_intent_id == pi_id
        )
    )
    payment_link = result.scalar_one_or_none()
    if payment_link:
        payment_link.status = PaymentLinkStatus.COMPLETED
        payment_link.paid_at = datetime.now(timezone.utc)

    # Record the payment on the invoice
    if invoice_id_str:
        invoice_uuid = uuid.UUID(invoice_id_str)
        inv_result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.payments))
            .where(Invoice.id == invoice_uuid)
        )
        invoice = inv_result.scalar_one_or_none()
        if invoice and await _connect_account_mismatch(db, invoice.created_by, expected_connect_account_id):
            return
        if invoice:
            amount_paid = Decimal(str(payment_intent.get("amount_received", 0))) / Decimal('100')

            # Check for duplicate payment (idempotency)
            existing_refs = {p.reference for p in (invoice.payments or []) if p.reference}
            if pi_id in existing_refs:
                return

            payment = InvoicePayment(
                invoice_id=invoice.id,
                amount=amount_paid,
                date=date_type.today(),
                payment_method="stripe",
                reference=pi_id,
                recorded_by=invoice.created_by,
            )
            db.add(payment)

            total_paid = sum((Decimal(str(p.amount)) for p in (invoice.payments or [])), Decimal('0')) + amount_paid
            if total_paid >= invoice.total:
                invoice.status = InvoiceStatus.PAID
            else:
                invoice.status = InvoiceStatus.PARTIALLY_PAID

            # Create income record
            from app.income.models import Income, IncomeCategory

            income = Income(
                contact_id=invoice.contact_id,
                invoice_id=invoice.id,
                category=IncomeCategory.INVOICE_PAYMENT,
                description=f"Stripe payment for Invoice {invoice.invoice_number}",
                amount=amount_paid,
                currency=invoice.currency,
                date=date_type.today(),
                payment_method="stripe",
                reference=pi_id,
                created_by=invoice.created_by,
            )
            db.add(income)

            # OBRAIN_EVENT_SPEC.md §3 — embedded-checkout invoice payment.
            owner = await db.get(User, invoice.created_by)
            if owner is not None:
                await emit_event(
                    db,
                    event="payment_processed",
                    org_id=resolve_org_id(owner),
                    properties={"amountUSD": float(amount_paid), "source": "invoice"},
                )

    await db.commit()


async def _handle_subscription_payment(
    db: AsyncSession, invoice: dict, expected_connect_account_id: str | None = None
) -> None:
    """When a subscription payment succeeds, create an income record."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == subscription_id
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return
    if await _connect_account_mismatch(db, sub.created_by, expected_connect_account_id):
        return

    from app.income.models import Income, IncomeCategory
    from datetime import date as date_type

    amount = Decimal(str(invoice.get("amount_paid", 0))) / Decimal('100')

    income = Income(
        contact_id=sub.contact_id,
        category=IncomeCategory.SERVICE,
        description=f"Subscription payment: {sub.name}",
        amount=amount,
        currency=sub.currency,
        date=date_type.today(),
        payment_method="stripe",
        reference=invoice.get("id"),
        created_by=sub.created_by,
    )
    db.add(income)

    # Update period end
    if invoice.get("lines", {}).get("data"):
        line = invoice["lines"]["data"][0]
        if line.get("period", {}).get("end"):
            sub.current_period_end = datetime.fromtimestamp(
                line["period"]["end"], tz=timezone.utc
            )

    await db.commit()


async def _handle_subscription_cancelled(
    db: AsyncSession, subscription: dict, expected_connect_account_id: str | None = None
) -> None:
    """When a subscription is cancelled from Stripe's side."""
    sub_id = subscription.get("id")
    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub and await _connect_account_mismatch(db, sub.created_by, expected_connect_account_id):
        return
    if sub:
        sub.status = SubscriptionStatus.CANCELLED
        await db.commit()
