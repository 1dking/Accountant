"""Account subscription billing — the customer paying for their O-Brain plan.

Prices come from the platform-admin pricing settings (plan_pro_price, etc.),
so the owner controls them in one place. Stripe Checkout runs in
subscription mode with inline price_data, so no Stripe Products/Prices need
to be pre-created. Activation uses both a webhook hook and a verify-on-return
path (the same belt-and-suspenders as proposal payments)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import AccountSubscription
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

PLAN_KEYS = ("starter", "pro", "business", "enterprise")
PLAN_NAMES = {
    "starter": "Starter",
    "pro": "Professional",
    "business": "Business",
    "enterprise": "Enterprise",
}


async def _pricing(db: AsyncSession) -> dict[str, str]:
    from app.platform_admin.service import list_platform_settings

    rows = await list_platform_settings(db, "pricing")
    return {r.key: r.value for r in rows}


def _plan_amount(pricing: dict[str, str], plan_key: str, period: str) -> float:
    """The plan's MONTHLY rate for the chosen period. Annual settings are stored
    as '$/mo billed yearly', so this is a per-month figure either way — see
    _charge_amount for what Stripe actually bills."""
    key = f"plan_{plan_key}_annual_price" if period == "annual" else f"plan_{plan_key}_price"
    raw = pricing.get(key) or pricing.get(f"plan_{plan_key}_price") or "0"
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _charge_amount(monthly_rate: float, period: str) -> float:
    """What Stripe charges per billing interval. Annual plans bill 12x the
    stored per-month rate once a year — the settings are '$/mo billed yearly',
    which is also how the UI presents them ('billed yearly ($X*12/yr)')."""
    return monthly_rate * 12 if period == "annual" else monthly_rate


async def get_subscription(db: AsyncSession, user: User) -> AccountSubscription:
    result = await db.execute(
        select(AccountSubscription).where(AccountSubscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = AccountSubscription(user_id=user.id, plan_key="starter", status="active")
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


async def create_checkout(
    db: AsyncSession, user: User, plan_key: str, period: str, settings, base_url: str
) -> dict:
    if plan_key not in PLAN_KEYS:
        raise ValidationError(f"Unknown plan: {plan_key}")

    sub = await get_subscription(db, user)
    pricing = await _pricing(db)
    monthly_rate = _plan_amount(pricing, plan_key, period)

    # Starter is the free tier by design — switch with no payment.
    if plan_key == "starter":
        sub.plan_key = plan_key
        sub.status = "active"
        sub.billing_period = None
        sub.stripe_subscription_id = None
        await db.commit()
        return {"free": True, "plan_key": plan_key}

    # A paid plan priced at $0 is a misconfiguration, not a free plan. Failing
    # loudly beats silently giving the product away.
    if monthly_rate <= 0:
        raise ValidationError(
            f"Pricing for the {PLAN_NAMES[plan_key]} plan is not configured. "
            "Set it in Platform Admin → Pricing & Limits."
        )

    # Annual is stored as '$/mo billed yearly', so it must be cheaper per month
    # than monthly. If it isn't, the pricing table is wrong — refuse rather than
    # overcharge on a yearly commitment.
    if period == "annual":
        monthly_price = _plan_amount(pricing, plan_key, "monthly")
        if monthly_price > 0 and monthly_rate >= monthly_price:
            raise ValidationError(
                f"Annual pricing for the {PLAN_NAMES[plan_key]} plan is misconfigured "
                f"(${monthly_rate:g}/mo annual vs ${monthly_price:g}/mo monthly). "
                "Fix it in Platform Admin → Pricing & Limits, or choose monthly."
            )

    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key

    if not sub.stripe_customer_id:
        customer = stripe_lib.Customer.create(email=user.email, name=user.full_name)
        sub.stripe_customer_id = customer.id
        await db.commit()

    origin = base_url.rstrip("/") if base_url else settings.public_base_url
    interval = "year" if period == "annual" else "month"
    charge = _charge_amount(monthly_rate, period)

    session = stripe_lib.checkout.Session.create(
        mode="subscription",
        customer=sub.stripe_customer_id,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"O-Brain {PLAN_NAMES[plan_key]}"},
                "unit_amount": int(round(charge * 100)),
                "recurring": {"interval": interval},
            },
            "quantity": 1,
        }],
        metadata={"user_id": str(user.id), "plan_key": plan_key, "period": period, "kind": "account_subscription"},
        subscription_data={
            "metadata": {"user_id": str(user.id), "plan_key": plan_key, "kind": "account_subscription"}
        },
        success_url=f"{origin}/settings?tab=billing&sub=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/settings?tab=billing&sub=cancelled",
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def _activate_from_subscription(
    db: AsyncSession, sub: AccountSubscription, plan_key: str, stripe_sub, period: str | None
) -> None:
    sub.plan_key = plan_key
    sub.status = "active"
    if period:
        sub.billing_period = period
    sub.stripe_subscription_id = getattr(stripe_sub, "id", None) or (
        stripe_sub.get("id") if isinstance(stripe_sub, dict) else None
    )
    cpe = None
    if isinstance(stripe_sub, dict):
        cpe = stripe_sub.get("current_period_end")
    else:
        cpe = getattr(stripe_sub, "current_period_end", None)
    if cpe:
        sub.current_period_end = datetime.fromtimestamp(int(cpe), tz=timezone.utc)
    await db.commit()


async def verify_checkout(db: AsyncSession, user: User, session_id: str, settings) -> dict:
    """On return from Stripe, confirm the subscription and apply the plan —
    works even if the webhook is misconfigured."""
    sub = await get_subscription(db, user)
    if not settings.stripe_secret_key or not session_id:
        return _payload(sub)

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key
    try:
        session = stripe_lib.checkout.Session.retrieve(session_id)
    except Exception:  # noqa: BLE001
        logger.exception("billing verify: retrieve failed for %s", session_id)
        return _payload(sub)

    md = session.get("metadata") or {}
    if md.get("kind") != "account_subscription" or md.get("user_id") != str(user.id):
        return _payload(sub)
    if session.get("status") == "complete" and session.get("subscription"):
        stripe_sub = stripe_lib.Subscription.retrieve(session["subscription"])
        await _activate_from_subscription(db, sub, md.get("plan_key", "pro"), stripe_sub, md.get("period"))
    return _payload(await get_subscription(db, user))


async def create_portal(db: AsyncSession, user: User, settings, return_url: str) -> dict:
    sub = await get_subscription(db, user)
    if not sub.stripe_customer_id:
        raise ValidationError("No billing account yet — subscribe to a paid plan first")
    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key
    session = stripe_lib.billing_portal.Session.create(
        customer=sub.stripe_customer_id, return_url=return_url
    )
    return {"url": session.url}


async def handle_stripe_event(db: AsyncSession, event_type: str, obj: dict) -> None:
    """Webhook hook for subscription lifecycle. No-ops for anything that
    isn't an account subscription, so it's safe to call for every event."""
    if event_type == "checkout.session.completed":
        md = obj.get("metadata") or {}
        if md.get("kind") != "account_subscription":
            return
        uid = md.get("user_id")
        if not uid:
            return
        result = await db.execute(select(AccountSubscription).where(AccountSubscription.user_id == uuid.UUID(uid)))
        sub = result.scalar_one_or_none()
        if sub and obj.get("subscription"):
            import stripe as stripe_lib

            stripe_sub = stripe_lib.Subscription.retrieve(obj["subscription"])
            await _activate_from_subscription(db, sub, md.get("plan_key", "pro"), stripe_sub, md.get("period"))

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub_id = obj.get("id")
        if not sub_id:
            return
        result = await db.execute(
            select(AccountSubscription).where(AccountSubscription.stripe_subscription_id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            return
        if event_type == "customer.subscription.deleted" or obj.get("status") in ("canceled", "unpaid"):
            sub.plan_key = "starter"
            sub.status = "canceled"
            sub.stripe_subscription_id = None
            sub.current_period_end = None
        else:
            sub.status = obj.get("status", sub.status)
            cpe = obj.get("current_period_end")
            if cpe:
                sub.current_period_end = datetime.fromtimestamp(int(cpe), tz=timezone.utc)
        await db.commit()


def _payload(sub: AccountSubscription) -> dict:
    return {
        "plan_key": sub.plan_key,
        "status": sub.status,
        "billing_period": sub.billing_period,
        "current_period_end": sub.current_period_end,
        "has_stripe_customer": bool(sub.stripe_customer_id),
    }
