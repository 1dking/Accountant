import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class AccountSubscription(TimestampMixin, Base):
    """A workspace's subscription to O-Brain itself (the SaaS plan the
    customer pays for). One row per account owner. plan_key is the source
    of truth for the current plan; Stripe fields are null on the free tier."""

    __tablename__ = "account_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    plan_key: Mapped[str] = mapped_column(String(20), default="starter")  # starter|pro|business|enterprise
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|canceled|past_due|incomplete
    billing_period: Mapped[str | None] = mapped_column(String(10), nullable=True)  # monthly|annual
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiUsage(TimestampMixin, Base):
    """Per-tenant, per-month AI spend meter.

    One row per (tenant, billing month). ``credits_used`` is an integer where
    **1 credit = $0.001** of estimated model spend, so a Claude chat message
    (~$0.018) costs 18 credits. Integers avoid float drift under concurrent
    increments.

    tenant_key mirrors ``events.service.resolve_org_id`` — the organisation id
    when the user belongs to one, otherwise the user's own id — so an agency
    with staff meters as ONE tenant rather than per-seat.
    """

    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "YYYY-MM"
    credits_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("tenant_key", "period", name="uq_ai_usage_tenant_period"),
    )


class TelephonyAccount(TimestampMixin, Base):
    """A tenant's own Twilio subaccount.

    Isolation boundary: every number, call and message for this tenant runs on
    ITS credentials, never the parent account's. ``suspended_at`` is the kill
    switch — set by a usage trigger breaching the hard cap, cleared only from
    platform admin.
    """

    __tablename__ = "telephony_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subaccount_sid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    encrypted_auth_token: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Per-tenant hard ceilings. NULL = fall back to the platform default.
    max_numbers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_spend_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_spend_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_permissions_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Least-privilege capability grants (Step 2) -------------------------
    # DEFAULT OFF, every one of them. Creating a subaccount grants NOTHING; an
    # operator turns on exactly the capabilities that tenant should have (voice
    # yes / SMS no, or the reverse). Enforced server-side on every telephony
    # endpoint via telephony.require_capability() — a tenant cannot self-escalate
    # because nothing in the tenant-facing API writes these columns.
    allow_voice_outbound: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    allow_voice_inbound: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    allow_sms: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    allow_mms: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    #: Buying numbers is itself a privilege, separate from using them.
    allow_number_purchase: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    #: Who last changed the grants, for the audit trail.
    capabilities_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    capabilities_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Markup rights are a paid-tier privilege (Step 5). OFF = at-cost
    #: pass-through; ON = this operator may set retail above our cost and keep
    #: the spread.
    allow_markup: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )


# ---------------------------------------------------------------------------
# Telephony rebilling
#
# Money is stored as INTEGER MICRO-DOLLARS (1e-6 USD) everywhere below.
# Telephony rates are fractions of a cent ($0.0079/SMS = 7_900 micros), so
# floats would drift across millions of small debits. Dollars are produced
# only at the API boundary.
# ---------------------------------------------------------------------------

MICROS_PER_USD = 1_000_000


class TelephonyRate(TimestampMixin, Base):
    """One row of the rate card: what a unit costs us, and what we sell it for.

    Resolution is most-specific-wins:
        tenant override -> plan override -> global unit row -> global markup

    ``sell_price_micros`` NULL means "derive from markup_multiplier", so an
    operator can run a blanket 2.5x and still pin individual units.
    """

    __tablename__ = "telephony_rates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    #: "global" | "plan" | "tenant"
    scope: Mapped[str] = mapped_column(String(10), nullable=False, default="global")
    #: NULL for global; plan_key for plan scope; tenant_key for tenant scope.
    scope_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    our_cost_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sell_price_micros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    markup_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: False switches a unit off for this scope entirely - this is how
    #: "Pro does not get telephony" is expressed.
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("scope", "scope_key", "unit", name="uq_telephony_rate_scope_unit"),
    )


class TelephonyCredit(TimestampMixin, Base):
    """Prepaid telephony balance for one tenant.

    Prepaid by design: we never front more than the tenant has bought. That is
    simultaneously fraud protection (a stolen account can only burn what was
    paid for) and collection protection (nothing to chase after the fact).
    """

    __tablename__ = "telephony_credits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    balance_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lifetime_purchased_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lifetime_spent_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    auto_topup_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    auto_topup_threshold_micros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_topup_amount_micros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_method_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_topup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    low_balance_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelephonyLedgerEntry(TimestampMixin, Base):
    """Every credit and debit, with OUR cost recorded beside what we BILLED.

    Keeping both on one row is what makes realised margin a query rather than
    an estimate - the whole point of the rebilling exercise.
    """

    __tablename__ = "telephony_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    #: "usage" | "topup" | "a2p_fee" | "adjustment" | "refund"
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    our_cost_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Negative for top-ups (money in), positive for usage (money out).
    billed_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_after_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Twilio usage record SID or Stripe session id. UNIQUE, so re-running the
    #: metering job can never double-bill the same usage.
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_telephony_ledger_tenant_period", "tenant_key", "period"),
    )


class A2PRegistration(TimestampMixin, Base):
    """A2P 10DLC registration state for one tenant.

    US carriers require brand + campaign registration before a 10-digit number
    may send application-to-person SMS. Campaign review takes 10-15 days, so
    the tenant needs a visible waiting state, and SMS stays locked until
    ``status == "approved"``.
    """

    __tablename__ = "a2p_registrations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: not_started | profile_pending | brand_pending | campaign_pending
    #: | approved | rejected
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="not_started", server_default="not_started"
    )

    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sample_messages_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    campaign_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
