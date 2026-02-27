from __future__ import annotations

import uuid
from datetime import datetime, timezone

import stripe as stripe_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError

from .models import (
    PaymentLinkStatus,
    StripePaymentLink,
    StripeSubscription,
    SubscriptionInterval,
    SubscriptionStatus,
)
from .schemas import CreateSubscriptionRequest


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
) -> StripePaymentLink:
    """Create a Stripe Checkout Session for an invoice."""
    from app.invoicing.models import Invoice

    _configure_stripe(settings)

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError(f"Invoice {invoice_id} not found")

    amount_cents = int(round(invoice.total * 100))

    session = stripe_lib.checkout.Session.create(
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
        success_url="http://localhost:5173/invoices?payment=success",
        cancel_url="http://localhost:5173/invoices?payment=cancelled",
        metadata={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
        },
    )

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
    return result.scalar_one_or_none()


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
    amount_cents = int(round(data.amount * 100))

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
    elif event_type == "invoice.payment_succeeded":
        await _handle_subscription_payment(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_cancelled(db, data_object)

    return {"event_type": event_type, "handled": True}


async def _handle_checkout_completed(
    db: AsyncSession, session: dict
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
        if invoice:
            payment = InvoicePayment(
                invoice_id=invoice.id,
                amount=float(session.get("amount_total", 0)) / 100,
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
                amount=float(session.get("amount_total", 0)) / 100,
                currency=invoice.currency,
                date=date_type.today(),
                payment_method="stripe",
                reference=session.get("payment_intent"),
                created_by=invoice.created_by,
            )
            db.add(income)

    await db.commit()


async def _handle_subscription_payment(
    db: AsyncSession, invoice: dict
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

    from app.income.models import Income, IncomeCategory
    from datetime import date as date_type

    amount = float(invoice.get("amount_paid", 0)) / 100

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
    db: AsyncSession, subscription: dict
) -> None:
    """When a subscription is cancelled from Stripe's side."""
    sub_id = subscription.get("id")
    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.CANCELLED
        await db.commit()
