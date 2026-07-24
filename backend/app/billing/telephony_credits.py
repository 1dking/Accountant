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
    from app.communication.a2p import is_exempt_account
    from app.config import Settings

    settings = Settings()
    if not settings.telephony_enforce_credit:
        return
    # Operator-owned accounts bypass enforcement entirely.
    if is_exempt_account(user, settings):
        return

    from app.billing.rate_card import require_enabled

    rate = await require_enabled(db, user, unit)
    row = await get_or_create(db, user)
    needed = int(round(rate.sell_price_micros * quantity))

    if row.balance_micros <= 0 or row.balance_micros < needed:
        raise InsufficientTelephonyCredit(row.balance_micros, needed, action)


async def enforce_spend_caps(db: AsyncSession, user: User) -> None:
    """Block when the tenant is over its daily or monthly telephony spend cap.

    Reads the caps stored on TelephonyAccount (previously displayed but never
    enforced) and compares them to billed spend in the ledger. No provisioned
    subaccount -> no caps yet. Raises TelephonyCapReached (402).
    """
    from sqlalchemy import func

    from app.billing.ai_meter import tenant_key_for
    from app.billing.models import TelephonyAccount
    from app.communication.telephony import (
        TelephonyCapReached,
        daily_cap_for,
        monthly_cap_for,
    )

    tenant = tenant_key_for(user)
    account = (
        await db.execute(
            select(TelephonyAccount).where(TelephonyAccount.tenant_key == tenant)
        )
    ).scalar_one_or_none()
    if account is None:
        return

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = current_period(now)

    async def _billed_since(since: datetime | None = None, period: str | None = None) -> int:
        q = select(func.coalesce(func.sum(TelephonyLedgerEntry.billed_micros), 0)).where(
            TelephonyLedgerEntry.tenant_key == tenant,
            TelephonyLedgerEntry.entry_type.in_(("usage", "a2p_fee")),
        )
        if since is not None:
            q = q.where(TelephonyLedgerEntry.created_at >= since)
        if period is not None:
            q = q.where(TelephonyLedgerEntry.period == period)
        return int(await db.scalar(q) or 0)

    daily_cap = int(daily_cap_for(account) * MICROS_PER_USD)
    if daily_cap > 0 and await _billed_since(since=day_start) >= daily_cap:
        raise TelephonyCapReached(
            f"Daily telephony spend cap of ${daily_cap / MICROS_PER_USD:.2f} reached. "
            "It resets at midnight UTC, or an admin can raise it.",
            resource="daily_spend_cap",
        )

    monthly_cap = int(monthly_cap_for(account) * MICROS_PER_USD)
    if monthly_cap > 0 and await _billed_since(period=month) >= monthly_cap:
        raise TelephonyCapReached(
            f"Monthly telephony spend cap of ${monthly_cap / MICROS_PER_USD:.2f} reached. "
            "Contact an admin to raise it.",
            resource="monthly_spend_cap",
        )


async def debit_now(
    db: AsyncSession,
    user: User,
    *,
    unit: str,
    action: str,
    quantity: float = 1.0,
    description: str | None = None,
) -> int:
    """Charge outbound telephony against prepaid credit SYNCHRONOUSLY.

    This is the real spend wall: it atomically decrements the balance BEFORE
    the message/call goes out, so a funded account can no longer send an
    unbounded burst at a frozen balance (the old ``require_credit`` only read).

    Order of gates: staging flag / exemption -> plan enabled -> spend caps ->
    atomic balance decrement. Raises 402 (InsufficientTelephonyCredit) or 403
    (TelephonyNotAvailable) / 402 (TelephonyCapReached). Returns credits
    charged (0 when metering is off or the account is exempt).

    The daily metering job SKIPS the units debited here (see
    telephony_metering.LIVE_DEBITED_CATEGORIES), so there is no double-charge.
    """
    import uuid as _uuid

    from app.communication.a2p import is_exempt_account
    from app.config import Settings

    settings = Settings()
    if not settings.telephony_enforce_credit:
        return 0
    if is_exempt_account(user, settings):
        return 0

    from app.billing.rate_card import require_enabled

    rate = await require_enabled(db, user, unit)  # 403 if plan has no telephony
    await enforce_spend_caps(db, user)

    row = await get_or_create(db, user)
    needed = int(round(rate.sell_price_micros * quantity))
    cost = int(round(rate.our_cost_micros * quantity))

    # Atomic conditional decrement: only succeeds while balance covers the
    # charge, so two concurrent sends can't both pass on the same dollar.
    result = await db.execute(
        update(TelephonyCredit)
        .where(
            TelephonyCredit.tenant_key == row.tenant_key,
            TelephonyCredit.balance_micros >= needed,
        )
        .values(
            balance_micros=TelephonyCredit.balance_micros - needed,
            lifetime_spent_micros=TelephonyCredit.lifetime_spent_micros + needed,
        )
    )
    if (result.rowcount or 0) == 0:
        raise InsufficientTelephonyCredit(row.balance_micros, needed, action)

    new_balance = await get_balance_micros(db, row.tenant_key)
    db.add(TelephonyLedgerEntry(
        tenant_key=row.tenant_key,
        period=current_period(),
        entry_type="usage",
        unit=unit,
        quantity=quantity,
        our_cost_micros=cost,
        billed_micros=needed,
        balance_after_micros=new_balance,
        external_ref=f"live:{_uuid.uuid4().hex}",
        description=description or f"{unit} x{quantity:g}",
    ))
    await db.commit()
    return needed


async def safe_debit(db: AsyncSession, user: User, *, unit: str, quantity: float = 1.0) -> bool:
    """Background/automated variant: debit if possible, else DON'T send.

    Automated inbound-reply senders must not raise a 402 at nobody, but at zero
    balance they must still stop spending. Returns True if the caller may send.
    """
    try:
        await debit_now(db, user, unit=unit, action="send", quantity=quantity)
        return True
    except (InsufficientTelephonyCredit,) as exc:  # noqa: F841
        logger.info("telephony: automated send skipped — no credit for %s", unit)
        return False
    except Exception:  # noqa: BLE001 — plan/cap gates: don't send, don't crash the job
        logger.info("telephony: automated send skipped — telephony gate for %s", unit)
        return False


async def safe_debit_by_user_id(db: AsyncSession, user_id, *, unit: str, quantity: float = 1.0) -> bool:
    """:func:`safe_debit` for automated senders that only carry a user id.

    Unknown user -> do not send (fail closed): an unattributable automated send
    can't be billed to anyone, so it must not go out.
    """
    if user_id is None:
        return False
    user = await db.get(User, user_id)
    if user is None:
        logger.warning("telephony: automated send blocked — user %s not found", user_id)
        return False
    return await safe_debit(db, user, unit=unit, quantity=quantity)


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
