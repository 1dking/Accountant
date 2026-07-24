"""Prepaid telephony credits: balance, debits, top-ups, auto top-up.

Prepaid is deliberate. We never front more than the tenant has bought, so a
compromised account can only burn credit that was already paid for, and there
is never an unpaid usage invoice to chase. Fraud protection and collection
protection are the same mechanism here.

At zero balance:
  * outbound calls and SMS are blocked,
  * number renewal is blocked (the recurring cost stops),
  * inbound keeps working — cutting off someone's incoming calls over a $2
    balance is a worse failure than eating $2.

All money is integer micro-dollars; see models.MICROS_PER_USD.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import (
    MICROS_PER_USD,
    TelephonyCredit,
    TelephonyLedgerEntry,
)
from app.billing.rate_card import ResolvedRate, usd
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

#: Warn the tenant below this. Not a block — just a nudge to top up.
LOW_BALANCE_MICROS = 2 * MICROS_PER_USD  # $2.00

#: Minimum and maximum a tenant may buy in one go.
MIN_TOPUP_MICROS = 5 * MICROS_PER_USD
MAX_TOPUP_MICROS = 500 * MICROS_PER_USD


class InsufficientTelephonyCredit(AppError):
    """402 — out of prepaid telephony credit."""

    def __init__(self, balance_micros: int, needed_micros: int, action: str):
        super().__init__(
            code="INSUFFICIENT_TELEPHONY_CREDIT",
            message=(
                f"Not enough telephony credit to {action}. "
                f"Balance ${usd(max(0, balance_micros)):.2f}, "
                f"this needs ${usd(needed_micros):.2f}. "
                "Top up to continue — incoming calls and texts keep working."
            ),
            status_code=402,
        )
        self.balance_micros = balance_micros
        self.needed_micros = needed_micros


def current_period(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


async def get_or_create(db: AsyncSession, user: User) -> TelephonyCredit:
    from app.billing.ai_meter import tenant_key_for

    tenant = tenant_key_for(user)
    result = await db.execute(
        select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = TelephonyCredit(tenant_key=tenant, owner_user_id=user.id, balance_micros=0)
        db.add(row)
        try:
            await db.commit()
        except Exception:  # noqa: BLE001 — lost a race
            await db.rollback()
            result = await db.execute(
                select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant)
            )
            row = result.scalar_one()
        else:
            await db.refresh(row)
    return row


async def get_balance_micros(db: AsyncSession, tenant_key: str) -> int:
    result = await db.execute(
        select(TelephonyCredit.balance_micros).where(TelephonyCredit.tenant_key == tenant_key)
    )
    return result.scalar_one_or_none() or 0


async def summary(db: AsyncSession, user: User) -> dict:
    """Balance view for the tenant's billing screen."""
    row = await get_or_create(db, user)
    return {
        "balance_usd": usd(row.balance_micros),
        "is_low": row.balance_micros < LOW_BALANCE_MICROS,
        "is_empty": row.balance_micros <= 0,
        "lifetime_purchased_usd": usd(row.lifetime_purchased_micros),
        "lifetime_spent_usd": usd(row.lifetime_spent_micros),
        "auto_topup_enabled": row.auto_topup_enabled,
        "auto_topup_threshold_usd": usd(row.auto_topup_threshold_micros or 0),
        "auto_topup_amount_usd": usd(row.auto_topup_amount_micros or 0),
        "has_payment_method": bool(row.stripe_payment_method_id),
    }


# ---------------------------------------------------------------------------
# Debits
# ---------------------------------------------------------------------------


async def charge(
    db: AsyncSession,
    tenant_key: str,
    *,
    unit: str,
    quantity: float,
    rate: ResolvedRate,
    external_ref: str | None = None,
    description: str | None = None,
    allow_negative: bool = True,
) -> TelephonyLedgerEntry | None:
    """Debit the balance for metered usage and write the ledger row.

    ``allow_negative`` defaults True for *observed* usage: Twilio has already
    delivered the message by the time we meter it, so refusing to record it
    would only hide the debt. The block happens BEFORE sending (see
    :func:`require_credit`), not here.

    Idempotent on ``external_ref`` — re-running the metering job cannot
    double-bill the same Twilio usage record.
    """
    if external_ref:
        existing = await db.execute(
            select(TelephonyLedgerEntry).where(
                TelephonyLedgerEntry.external_ref == external_ref
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None  # already metered

    billed = int(round(rate.sell_price_micros * quantity))
    cost = int(round(rate.our_cost_micros * quantity))

    result = await db.execute(
        select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant_key)
    )
    credit = result.scalar_one_or_none()
    if credit is None:
        logger.warning("telephony_credits: no credit row for tenant %s", tenant_key)
        return None

    new_balance = credit.balance_micros - billed
    if new_balance < 0 and not allow_negative:
        raise InsufficientTelephonyCredit(credit.balance_micros, billed, f"use {unit}")

    await db.execute(
        update(TelephonyCredit)
        .where(TelephonyCredit.tenant_key == tenant_key)
        .values(
            balance_micros=TelephonyCredit.balance_micros - billed,
            lifetime_spent_micros=TelephonyCredit.lifetime_spent_micros + billed,
        )
    )

    entry = TelephonyLedgerEntry(
        tenant_key=tenant_key,
        period=current_period(),
        entry_type="a2p_fee" if unit.startswith("a2p_") else "usage",
        unit=unit,
        quantity=quantity,
        our_cost_micros=cost,
        billed_micros=billed,
        balance_after_micros=new_balance,
        external_ref=external_ref,
        description=description,
    )
    db.add(entry)
    await db.commit()
    return entry


async def require_credit(
    db: AsyncSession, user: User, *, unit: str, action: str, quantity: float = 1.0
) -> None:
    """Gate an outbound action on having credit. Raises 402 at zero.

    Called BEFORE sending — this is the point at which we decline to front
    money. Inbound paths never call this.

    Staged behind ``telephony_enforce_credit`` (default OFF): metering and the
    ledger record usage from day one, but the BLOCK only bites once the flag is
    flipped — after tenants have had a chance to buy credit.

    The flag short-circuits the PLAN gate too, deliberately: every existing
    account defaults to the starter plan, whose rate card disables telephony —
    so enforcing plan shape while the flag is off would hard-cut every current
    user on deploy, which is exactly what staging exists to prevent.
    """
    from app.config import Settings

    if not Settings().telephony_enforce_credit:
        return

    from app.billing.rate_card import require_enabled

    rate = await require_enabled(db, user, unit)
    row = await get_or_create(db, user)
    needed = int(round(rate.sell_price_micros * quantity))

    if row.balance_micros <= 0 or row.balance_micros < needed:
        raise InsufficientTelephonyCredit(row.balance_micros, needed, action)


# ---------------------------------------------------------------------------
# Top-ups
# ---------------------------------------------------------------------------


async def apply_topup(
    db: AsyncSession,
    tenant_key: str,
    amount_micros: int,
    *,
    external_ref: str | None = None,
    description: str = "Telephony credit top-up",
) -> TelephonyLedgerEntry | None:
    """Add purchased credit. Idempotent on ``external_ref`` (Stripe session id)."""
    if external_ref:
        existing = await db.execute(
            select(TelephonyLedgerEntry).where(
                TelephonyLedgerEntry.external_ref == external_ref
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None

    result = await db.execute(
        select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant_key)
    )
    credit = result.scalar_one_or_none()
    if credit is None:
        logger.warning("telephony_credits: top-up for unknown tenant %s", tenant_key)
        return None

    await db.execute(
        update(TelephonyCredit)
        .where(TelephonyCredit.tenant_key == tenant_key)
        .values(
            balance_micros=TelephonyCredit.balance_micros + amount_micros,
            lifetime_purchased_micros=TelephonyCredit.lifetime_purchased_micros + amount_micros,
            last_topup_at=datetime.now(timezone.utc),
            low_balance_notified_at=None,
        )
    )

    entry = TelephonyLedgerEntry(
        tenant_key=tenant_key,
        period=current_period(),
        entry_type="topup",
        quantity=1.0,
        our_cost_micros=0,
        billed_micros=-amount_micros,  # money in
        balance_after_micros=credit.balance_micros + amount_micros,
        external_ref=external_ref,
        description=description,
    )
    db.add(entry)
    await db.commit()
    logger.info(
        "telephony_credits: +$%.2f for tenant %s", usd(amount_micros), tenant_key
    )
    return entry


async def create_topup_checkout(
    db: AsyncSession, user: User, amount_usd: float, settings, base_url: str
) -> dict:
    """Stripe Checkout for a one-off credit purchase."""
    from app.billing.ai_meter import tenant_key_for
    from app.core.exceptions import ValidationError

    amount_micros = int(round(amount_usd * MICROS_PER_USD))
    if amount_micros < MIN_TOPUP_MICROS or amount_micros > MAX_TOPUP_MICROS:
        raise ValidationError(
            f"Top-up must be between ${usd(MIN_TOPUP_MICROS):.0f} and "
            f"${usd(MAX_TOPUP_MICROS):.0f}."
        )
    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured.")

    row = await get_or_create(db, user)

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key

    if not row.stripe_customer_id:
        customer = stripe_lib.Customer.create(email=user.email, name=user.full_name)
        row.stripe_customer_id = customer.id
        await db.commit()

    origin = (base_url or settings.public_base_url).rstrip("/")
    session = stripe_lib.checkout.Session.create(
        mode="payment",
        customer=row.stripe_customer_id,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "O-Brain telephony credit"},
                "unit_amount": int(round(amount_usd * 100)),
            },
            "quantity": 1,
        }],
        # Keep the card so auto top-up has something to charge later.
        payment_intent_data={"setup_future_usage": "off_session"},
        metadata={
            "kind": "telephony_topup",
            "tenant_key": tenant_key_for(user),
            "amount_micros": str(amount_micros),
        },
        success_url=f"{origin}/settings?tab=billing&topup=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/settings?tab=billing&topup=cancelled",
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def verify_topup(db: AsyncSession, user: User, session_id: str, settings) -> dict:
    """Confirm a top-up on return from Stripe, webhook-independent."""
    from app.billing.ai_meter import tenant_key_for

    if not settings.stripe_secret_key or not session_id:
        return await summary(db, user)

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key
    try:
        session = stripe_lib.checkout.Session.retrieve(session_id)
    except Exception:  # noqa: BLE001
        logger.exception("telephony_credits: could not retrieve session %s", session_id)
        return await summary(db, user)

    md = session.get("metadata") or {}
    tenant = tenant_key_for(user)
    if md.get("kind") != "telephony_topup" or md.get("tenant_key") != tenant:
        return await summary(db, user)
    if session.get("payment_status") == "paid":
        await apply_topup(
            db, tenant, int(md.get("amount_micros", 0)), external_ref=session_id
        )
    return await summary(db, user)


async def maybe_auto_topup(db: AsyncSession, tenant_key: str, settings) -> bool:
    """Charge the saved card when the balance falls below the threshold.

    Off-session, so it needs a payment method captured by an earlier manual
    top-up. Returns True if a charge was made.
    """
    result = await db.execute(
        select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant_key)
    )
    row = result.scalar_one_or_none()
    if row is None or not row.auto_topup_enabled:
        return False
    if not row.stripe_customer_id or not settings.stripe_secret_key:
        return False

    threshold = row.auto_topup_threshold_micros or LOW_BALANCE_MICROS
    amount = row.auto_topup_amount_micros or (20 * MICROS_PER_USD)
    if row.balance_micros > threshold:
        return False

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key
    try:
        intent = stripe_lib.PaymentIntent.create(
            amount=int(round(amount / MICROS_PER_USD * 100)),
            currency="usd",
            customer=row.stripe_customer_id,
            payment_method=row.stripe_payment_method_id,
            off_session=True,
            confirm=True,
            metadata={"kind": "telephony_topup_auto", "tenant_key": tenant_key},
        )
    except Exception:  # noqa: BLE001 — a declined card must not break metering
        logger.exception("telephony_credits: auto top-up failed for %s", tenant_key)
        return False

    await apply_topup(
        db, tenant_key, amount,
        external_ref=intent.id, description="Automatic top-up",
    )
    return True
