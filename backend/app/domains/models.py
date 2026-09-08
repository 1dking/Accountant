"""Domain reseller (S8) — domain purchases + DNS records.

We are the merchant of record; the customer pays us via Stripe, we buy
through the partner (Porkbun) with the platform's reseller creds, and
we own the DB row that says who owns which name. `partner_reference`
holds whatever the partner's own id is (Porkbun has no server-side id
for a name — it's the name itself — so this stores the domain again
for symmetry with providers that do issue one).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class DomainPurchase(TimestampMixin, Base):
    __tablename__ = "domain_purchases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)

    # domain name in punycode/lowercase (e.g. "example.com")
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    tld: Mapped[str] = mapped_column(String(64), index=True)

    partner: Mapped[str] = mapped_column(String(32), default="porkbun")
    partner_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # money is stored in cents to avoid float drift; wholesale = what we paid
    # the partner, price_paid = what the customer paid us via Stripe.
    price_cents_paid: Mapped[int] = mapped_column(Integer, default=0)
    price_cents_wholesale: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    years: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # pending | paid | registered | active | expired | failed | refunded
    stripe_checkout_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

    # partner-side error message on failure, freeform notes otherwise
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DnsRecord(TimestampMixin, Base):
    __tablename__ = "dns_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain_purchases.id", ondelete="CASCADE"), index=True)

    # partner-issued id — we need it to update/delete via the partner API
    partner_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    type: Mapped[str] = mapped_column(String(16))
    # A | AAAA | CNAME | MX | TXT | ALIAS | NS | CAA | SRV
    name: Mapped[str] = mapped_column(String(255), default="")
    # subdomain portion only ("www"), NOT the full FQDN — matches Porkbun's shape.
    content: Mapped[str] = mapped_column(Text)
    ttl: Mapped[int] = mapped_column(Integer, default=600)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


Index("ix_dns_records_domain_type", DnsRecord.domain_id, DnsRecord.type)
