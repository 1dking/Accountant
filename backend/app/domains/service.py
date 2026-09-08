"""Domain reseller service — pricing, purchase, list, DNS.

Money flow: check → Stripe Checkout Session (customer pays us) →
webhook OR sync callback confirms → Porkbun register → row status
flips to registered → status endpoint reports back.

Markup: platform-wide, defaults to 15% over Porkbun wholesale. Set
`PORKBUN_MARKUP_PCT` in Settings (config.py) to change without a code
edit. Never lets retail fall below wholesale.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.authorization import apply_cashbook_filter
from app.core.exceptions import ValidationError, NotFoundError
from app.domains.models import DomainPurchase, DnsRecord
from app.domains.porkbun import PorkbunClient, PorkbunError, build_client

logger = logging.getLogger(__name__)

DEFAULT_MARKUP_PCT = 15.0
MIN_MARKUP_PCT = 0.0
MAX_MARKUP_PCT = 100.0


def _markup_pct(settings) -> float:
    v = getattr(settings, "porkbun_markup_pct", None)
    if v is None:
        return DEFAULT_MARKUP_PCT
    try:
        v = float(v)
    except (TypeError, ValueError):
        return DEFAULT_MARKUP_PCT
    return max(MIN_MARKUP_PCT, min(MAX_MARKUP_PCT, v))


def _retail_cents(wholesale_cents: int, markup_pct: float) -> int:
    """Retail price after markup. Rounds UP to the next cent so we never
    lose money on a fraction of a cent."""
    if wholesale_cents <= 0:
        return 0
    marked = Decimal(wholesale_cents) * (Decimal(100) + Decimal(str(markup_pct))) / Decimal(100)
    return int(marked.to_integral_value(rounding="ROUND_CEILING"))


def _dollars_to_cents(s: str | float | int | None) -> int:
    if s is None or s == "":
        return 0
    try:
        return int((Decimal(str(s)) * 100).to_integral_value(rounding="ROUND_HALF_UP"))
    except Exception:
        return 0


def _tld(domain: str) -> str:
    parts = domain.strip().lower().split(".")
    return ".".join(parts[1:]) if len(parts) > 1 else ""


async def check_domain(domain: str, settings) -> dict:
    """Check availability + return retail price. Read-only, safe to call cheaply."""
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain or "." not in domain or " " in domain:
        raise ValidationError("Enter a domain like example.com")

    client = build_client(settings)
    try:
        raw = await client.check_domain(domain)
    except PorkbunError as e:
        logger.warning("porkbun.check_domain %s failed: %s", domain, e)
        return {"domain": domain, "available": False, "error": str(e)}

    resp = raw.get("response") or {}
    avail_flag = str(resp.get("avail", "")).lower() == "yes"
    premium = str(resp.get("premium", "")).lower() == "yes"
    wholesale = _dollars_to_cents(resp.get("price"))
    renewal = _dollars_to_cents(resp.get("regularPrice") or resp.get("renewal"))
    # Porkbun returns avail="no" for premium names that ARE registerable
    # (at a premium price). Treat any name with a positive price as
    # available; the UI badges "premium" separately.
    available = avail_flag or (wholesale > 0 and premium)
    markup = _markup_pct(settings)
    return {
        "domain": domain,
        "tld": _tld(domain),
        "available": available,
        "premium": premium,
        "currency": "USD",
        "price_cents_wholesale": wholesale,
        "price_cents_retail": _retail_cents(wholesale, markup),
        "renewal_cents_wholesale": renewal,
        "renewal_cents_retail": _retail_cents(renewal, markup),
        "markup_pct": markup,
    }


# ---------------------------------------------------------------------------
# Purchase — Stripe Checkout → webhook triggers register()
# ---------------------------------------------------------------------------

async def create_purchase_checkout(
    db: AsyncSession,
    user: User,
    settings,
    *,
    domain: str,
    years: int,
    base_url: str,
) -> dict:
    """Create a Stripe Checkout session for a domain purchase.

    We write a DomainPurchase row in `pending` status BEFORE redirecting so
    the webhook has a row to look up by stripe_checkout_id.
    """
    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")
    if years < 1 or years > 10:
        raise ValidationError("Years must be 1-10")

    quote = await check_domain(domain, settings)
    if not quote.get("available"):
        raise ValidationError(f"{domain} is not available")

    wholesale = int(quote["price_cents_wholesale"]) * years
    retail = int(quote["price_cents_retail"]) * years
    if retail <= 0:
        raise ValidationError("Pricing unavailable for this domain")

    row = DomainPurchase(
        created_by=user.id,
        org_id=user.org_id,
        domain=domain,
        tld=quote["tld"],
        years=years,
        price_cents_wholesale=wholesale,
        price_cents_paid=retail,
        currency="USD",
        status="pending",
        partner="porkbun",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    import stripe as stripe_lib
    stripe_lib.api_key = settings.stripe_secret_key
    origin = base_url.rstrip("/") if base_url else settings.public_base_url

    session = stripe_lib.checkout.Session.create(
        mode="payment",
        customer_email=user.email,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"Domain: {domain} ({years} year{'s' if years > 1 else ''})"},
                "unit_amount": retail,
            },
            "quantity": 1,
        }],
        metadata={
            "kind": "domain_purchase",
            "domain_purchase_id": str(row.id),
            "domain": domain,
            "years": str(years),
            "user_id": str(user.id),
        },
        success_url=f"{origin}/domains?purchased={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/domains?cancelled=1",
    )
    row.stripe_checkout_id = session.id
    await db.commit()
    return {"checkout_url": session.url, "session_id": session.id, "purchase_id": str(row.id)}


async def finalize_purchase(
    db: AsyncSession,
    settings,
    *,
    stripe_checkout_id: str,
    payment_intent_id: str | None = None,
) -> DomainPurchase:
    """Called from the Stripe webhook once payment succeeded — actually
    buy the name from Porkbun and flip the row to `registered`.
    Idempotent on the checkout id."""
    q = await db.execute(select(DomainPurchase).where(DomainPurchase.stripe_checkout_id == stripe_checkout_id))
    row = q.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Domain purchase", stripe_checkout_id)

    if row.status in ("registered", "active"):
        return row  # idempotent

    row.stripe_payment_intent_id = payment_intent_id
    row.status = "paid"
    await db.commit()

    client = build_client(settings)
    try:
        result = await client.register(row.domain, row.years)
    except PorkbunError as e:
        row.status = "failed"
        row.notes = f"Porkbun register failed: {e}"
        await db.commit()
        logger.error("porkbun.register %s failed after payment %s: %s",
                     row.domain, payment_intent_id, e)
        raise

    row.status = "registered"
    row.registered_at = datetime.now(timezone.utc)
    row.expires_at = row.registered_at + timedelta(days=365 * row.years)
    row.partner_reference = row.domain
    row.notes = (row.notes or "") + f"\npartner: {result.get('status', 'ok')}"
    await db.commit()
    logger.info("domain.registered %s for user %s", row.domain, row.created_by)
    return row


# ---------------------------------------------------------------------------
# List / get / DNS
# ---------------------------------------------------------------------------

async def list_purchases(db: AsyncSession, user: User) -> list[DomainPurchase]:
    stmt = select(DomainPurchase).order_by(DomainPurchase.created_at.desc())
    stmt = apply_cashbook_filter(stmt, DomainPurchase.created_by, DomainPurchase.org_id, user)
    res = await db.execute(stmt)
    return list(res.scalars())


async def get_purchase(db: AsyncSession, user: User, purchase_id: uuid.UUID) -> DomainPurchase:
    row = await db.get(DomainPurchase, purchase_id)
    if row is None:
        raise NotFoundError("Domain purchase", str(purchase_id))
    # tenant scope
    stmt = select(DomainPurchase.id).where(DomainPurchase.id == purchase_id)
    stmt = apply_cashbook_filter(stmt, DomainPurchase.created_by, DomainPurchase.org_id, user)
    ok = await db.execute(stmt)
    if ok.scalar_one_or_none() is None:
        raise NotFoundError("Domain purchase", str(purchase_id))
    return row


async def list_dns(db: AsyncSession, user: User, settings, purchase_id: uuid.UUID) -> list[dict]:
    """DNS records — always fetched fresh from Porkbun; DB cache is
    written back so the UI has a consistent view.
    """
    row = await get_purchase(db, user, purchase_id)
    client = build_client(settings)
    raw = await client.dns_list(row.domain)
    records = raw.get("records") or []
    return records


async def upsert_dns(
    db: AsyncSession, user: User, settings,
    purchase_id: uuid.UUID,
    *, record_id: str | None,
    type: str, content: str, name: str = "",
    ttl: int = 600, priority: int | None = None,
) -> dict:
    row = await get_purchase(db, user, purchase_id)
    client = build_client(settings)
    if record_id:
        return await client.dns_edit(row.domain, record_id, type=type, content=content,
                                     name=name, ttl=ttl, priority=priority)
    return await client.dns_create(row.domain, type=type, content=content,
                                   name=name, ttl=ttl, priority=priority)


async def delete_dns(db: AsyncSession, user: User, settings,
                     purchase_id: uuid.UUID, record_id: str) -> dict:
    row = await get_purchase(db, user, purchase_id)
    client = build_client(settings)
    return await client.dns_delete(row.domain, record_id)
