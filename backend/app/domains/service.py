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
from app.domains.models import DomainPurchase, DnsRecord, MailboxCredential
from app.domains.porkbun import PorkbunClient, PorkbunError, build_client
from app.domains.migadu import (
    MigaduError, build_client as build_migadu_client, migadu_dns_records,
)
from app.domains import imap_client
from app.core.encryption import get_encryption_service

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
    # Porkbun's API cannot register premium names — reject before charging.
    if quote.get("premium"):
        raise ValidationError(
            f"{domain} is a premium domain and cannot be registered "
            "through this checkout. Please choose a standard name."
        )
    # Porkbun API is 1-year-at-a-time; multi-year at purchase would require
    # follow-up renew() calls we haven't wired yet, so clamp for honesty.
    if years != 1:
        years = 1

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
    # Porkbun requires exact wholesale price (cents) to accept the buy.
    # Re-quote right before purchase so a stale price doesn't reject us.
    try:
        quote = await client.check_domain(row.domain)
    except PorkbunError as e:
        row.status = "failed"
        row.notes = f"Porkbun re-check failed: {e}"
        await db.commit()
        raise

    resp = quote.get("response") or {}
    wholesale_cents = _dollars_to_cents(resp.get("price"))
    if wholesale_cents <= 0:
        row.status = "failed"
        row.notes = "Porkbun returned no price on re-check"
        await db.commit()
        raise PorkbunError("Porkbun returned no price for domain")

    try:
        result = await client.register(row.domain, cost_cents=wholesale_cents)
    except PorkbunError as e:
        row.status = "failed"
        row.notes = f"Porkbun register failed: {e}"
        await db.commit()
        logger.error("porkbun.register %s failed after payment %s: %s",
                     row.domain, payment_intent_id, e)
        raise

    row.status = "registered"
    row.registered_at = datetime.now(timezone.utc)
    # API registrations are always 1 year — override any earlier row.years
    # so expires_at matches what actually happened at the registry.
    row.years = 1
    row.expires_at = row.registered_at + timedelta(days=365)
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


# ---------------------------------------------------------------------------
# Email hosting (Migadu). One-click "Enable email" adds the domain to
# Migadu AND writes the required MX/SPF/DKIM/DMARC records into the
# registrar's DNS so mail Just Works after propagation.
# ---------------------------------------------------------------------------

async def enable_email(
    db: AsyncSession, user: User, settings, purchase_id: uuid.UUID,
) -> dict:
    row = await get_purchase(db, user, purchase_id)
    if row.status not in ("registered", "active"):
        raise ValidationError("Domain must be registered before enabling email")

    migadu = build_migadu_client(settings)
    porkbun = build_client(settings)

    # 1. Add domain to Migadu (idempotent — 200 if it already exists,
    #    or the API returns "already exists" which we tolerate).
    try:
        await migadu.add_domain(row.domain)
    except MigaduError as e:
        if "exist" not in str(e).lower():
            raise
        logger.info("migadu.add_domain %s already existed, continuing", row.domain)

    # 2. Write DNS records via Porkbun. We skip any record whose (type,
    #    name, content) tuple already exists — some customers add MX by
    #    hand before clicking Enable and we don't want duplicates.
    existing_raw = await porkbun.dns_list(row.domain)
    existing = existing_raw.get("records") or []
    seen: set[tuple[str, str, str]] = {
        (str(r.get("type", "")).upper(), str(r.get("name", "")), str(r.get("content", "")))
        for r in existing
    }

    created, skipped = [], []
    for rec in migadu_dns_records(row.domain):
        # Porkbun stores names as the subdomain WITHOUT the base domain,
        # but returns them fully-qualified — normalise for the dedup check.
        fq_name = f"{rec['name']}.{row.domain}".lstrip(".") if rec["name"] else row.domain
        key = (rec["type"].upper(), fq_name, rec["content"])
        if key in seen or (rec["type"].upper(), rec["name"], rec["content"]) in seen:
            skipped.append(rec)
            continue
        try:
            await porkbun.dns_create(
                row.domain, type=rec["type"], content=rec["content"],
                name=rec["name"], ttl=rec.get("ttl", 3600),
                priority=rec.get("priority"),
            )
            created.append(rec)
        except PorkbunError as e:
            logger.warning("porkbun.dns_create %s %s failed: %s",
                           rec["type"], rec["name"], e)

    row.email_enabled = True
    await db.commit()
    return {
        "enabled": True,
        "records_created": len(created),
        "records_skipped": len(skipped),
        "note": "DNS propagates in ~15 minutes. Then add mailboxes.",
    }


async def email_status(db: AsyncSession, user: User, settings,
                       purchase_id: uuid.UUID) -> dict:
    """Report whether Migadu has activated the domain yet. Mailboxes can
    be created while inactive but can't authenticate (webmail/IMAP/SMTP)
    until Migadu's background DNS verification flips it active — 30 min
    to 24h after the records go live."""
    row = await get_purchase(db, user, purchase_id)
    if not row.email_enabled:
        return {"email_enabled": False, "active": False, "state": "not_enabled"}
    migadu = build_migadu_client(settings)
    try:
        d = await migadu.get_domain(row.domain)
    except MigaduError:
        return {"email_enabled": True, "active": False, "state": "unknown"}
    active = bool(d.get("can_access")) and str(d.get("state")) == "active"
    return {
        "email_enabled": True,
        "active": active,
        "state": d.get("state"),
        "can_send": bool(d.get("can_send")),
        "can_receive": bool(d.get("can_receive")),
    }


async def list_mailboxes(db: AsyncSession, user: User, settings,
                         purchase_id: uuid.UUID) -> list[dict]:
    row = await get_purchase(db, user, purchase_id)
    if not row.email_enabled:
        return []
    migadu = build_migadu_client(settings)
    return await migadu.list_mailboxes(row.domain)


async def create_mailbox(
    db: AsyncSession, user: User, settings, purchase_id: uuid.UUID,
    *, local_part: str, name: str, password: str,
) -> dict:
    row = await get_purchase(db, user, purchase_id)
    if not row.email_enabled:
        raise ValidationError("Enable email on this domain first")
    if not local_part or "@" in local_part or " " in local_part:
        raise ValidationError("Invalid mailbox name")
    if len(password) < 12:
        raise ValidationError("Password must be at least 12 characters")
    migadu = build_migadu_client(settings)
    result = await migadu.create_mailbox(
        row.domain, local_part=local_part.lower(), name=name, password=password,
    )
    await _store_credential(db, row, local_part.lower(), password)
    return result


async def delete_mailbox(db: AsyncSession, user: User, settings,
                         purchase_id: uuid.UUID, local_part: str) -> dict:
    row = await get_purchase(db, user, purchase_id)
    migadu = build_migadu_client(settings)
    return await migadu.delete_mailbox(row.domain, local_part.lower())


async def reset_mailbox_password(
    db: AsyncSession, user: User, settings, purchase_id: uuid.UUID,
    *, local_part: str, password: str,
) -> dict:
    row = await get_purchase(db, user, purchase_id)
    if len(password) < 12:
        raise ValidationError("Password must be at least 12 characters")
    migadu = build_migadu_client(settings)
    result = await migadu.update_mailbox_password(row.domain, local_part.lower(), password)
    await _store_credential(db, row, local_part.lower(), password)
    return result


async def _store_credential(db: AsyncSession, row: DomainPurchase,
                            local_part: str, password: str) -> None:
    """Encrypt + upsert the mailbox password so the CRM inbox can connect."""
    enc = get_encryption_service()
    address = f"{local_part}@{row.domain}"
    q = await db.execute(
        select(MailboxCredential).where(
            MailboxCredential.domain_id == row.id,
            MailboxCredential.local_part == local_part,
        )
    )
    cred = q.scalar_one_or_none()
    if cred is None:
        cred = MailboxCredential(
            domain_id=row.id, local_part=local_part, address=address,
            encrypted_password=enc.encrypt(password),
        )
        db.add(cred)
    else:
        cred.encrypted_password = enc.encrypt(password)
        cred.address = address
    await db.commit()


async def _load_credential(db: AsyncSession, row: DomainPurchase,
                           local_part: str) -> MailboxCredential:
    q = await db.execute(
        select(MailboxCredential).where(
            MailboxCredential.domain_id == row.id,
            MailboxCredential.local_part == local_part.lower(),
        )
    )
    cred = q.scalar_one_or_none()
    if cred is None:
        raise ValidationError(
            "This mailbox isn't connected to the inbox yet. Reset its "
            "password once from the Email page to link it."
        )
    return cred


# ---------------------------------------------------------------------------
# CRM inbox — read + send over IMAP/SMTP
# ---------------------------------------------------------------------------

async def inbox_list(db: AsyncSession, user: User, purchase_id: uuid.UUID,
                     local_part: str, *, folder: str = "INBOX", limit: int = 30) -> list[dict]:
    row = await get_purchase(db, user, purchase_id)
    cred = await _load_credential(db, row, local_part)
    pw = get_encryption_service().decrypt(cred.encrypted_password)
    return await imap_client.list_inbox(
        cred.imap_host, cred.imap_port, cred.address, pw, folder=folder, limit=limit,
    )


async def inbox_message(db: AsyncSession, user: User, purchase_id: uuid.UUID,
                        local_part: str, uid: str, *, folder: str = "INBOX") -> dict:
    row = await get_purchase(db, user, purchase_id)
    cred = await _load_credential(db, row, local_part)
    pw = get_encryption_service().decrypt(cred.encrypted_password)
    return await imap_client.get_message(
        cred.imap_host, cred.imap_port, cred.address, pw, uid, folder=folder,
    )


async def inbox_send(db: AsyncSession, user: User, purchase_id: uuid.UUID,
                     local_part: str, *, to: str, subject: str, body: str,
                     in_reply_to: str | None = None) -> dict:
    row = await get_purchase(db, user, purchase_id)
    cred = await _load_credential(db, row, local_part)
    pw = get_encryption_service().decrypt(cred.encrypted_password)
    return await imap_client.send_message(
        cred.smtp_host, cred.smtp_port, cred.address, pw,
        to=to, subject=subject, body=body, in_reply_to=in_reply_to,
    )
