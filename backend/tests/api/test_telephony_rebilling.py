"""Tests for telephony rebilling: rate card, prepaid credits, margin, A2P.

The commercial claim is "we mark telephony up and it is profitable". These
tests prove the mechanism that backs it: resolution order, markup maths,
prepaid enforcement, idempotent metering, and realised margin from the ledger.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing import rate_card, telephony_credits
from app.billing.models import (
    MICROS_PER_USD,
    TelephonyCredit,
    TelephonyLedgerEntry,
    TelephonyRate,
)


@pytest.fixture
def enforcement_on(monkeypatch):
    """Run a test with the staged rollout flags FLIPPED ON.

    The guards construct Settings() fresh per call, so env vars are the
    mechanism. Default state (flags off) is what production deploys with.
    """
    monkeypatch.setenv("TELEPHONY_ENFORCE_CREDIT", "true")
    monkeypatch.setenv("TELEPHONY_ENFORCE_A2P", "true")
    yield


async def _set_plan(db: AsyncSession, user: User, plan_key: str) -> None:
    from app.billing import service

    sub = await service.get_subscription(db, user)
    sub.plan_key = plan_key
    await db.commit()


async def _fund(db: AsyncSession, user: User, dollars: float) -> TelephonyCredit:
    row = await telephony_credits.get_or_create(db, user)
    row.balance_micros = int(dollars * MICROS_PER_USD)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Rate card
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_markup_derives_sell_price(db: AsyncSession):
    """With no pinned price, sell = cost x markup."""
    r = await rate_card.resolve_rate(db, "sms_outbound")
    assert r.our_cost_micros == rate_card.DEFAULT_COST_MICROS["sms_outbound"]
    assert r.sell_price_micros == int(round(r.our_cost_micros * rate_card.DEFAULT_MARKUP))
    assert r.margin_micros > 0
    assert r.source == "markup-default"


@pytest.mark.critical
async def test_pinned_sell_price_beats_markup(db: AsyncSession):
    await rate_card.upsert_rate(
        db, unit="sms_outbound", our_cost_usd=0.0079, sell_price_usd=0.05
    )
    r = await rate_card.resolve_rate(db, "sms_outbound")
    assert r.sell_price_micros == rate_card.to_micros(0.05)
    assert r.source == "global"
    # 0.05 sell on 0.0079 cost
    assert r.margin_pct > 80


@pytest.mark.critical
async def test_resolution_order_tenant_beats_plan_beats_global(db: AsyncSession):
    """Most-specific-wins is the whole point of the override system."""
    await rate_card.upsert_rate(db, unit="sms_outbound", sell_price_usd=0.05)
    await rate_card.upsert_rate(
        db, unit="sms_outbound", scope="plan", scope_key="business", sell_price_usd=0.03
    )
    await rate_card.upsert_rate(
        db, unit="sms_outbound", scope="tenant", scope_key="tenant-x", sell_price_usd=0.01
    )

    g = await rate_card.resolve_rate(db, "sms_outbound")
    assert g.sell_price_micros == rate_card.to_micros(0.05) and g.source == "global"

    p = await rate_card.resolve_rate(db, "sms_outbound", plan_key="business")
    assert p.sell_price_micros == rate_card.to_micros(0.03) and p.source == "plan"

    t = await rate_card.resolve_rate(
        db, "sms_outbound", tenant_key="tenant-x", plan_key="business"
    )
    assert t.sell_price_micros == rate_card.to_micros(0.01) and t.source == "tenant"


@pytest.mark.critical
async def test_plan_without_telephony_is_disabled(db: AsyncSession):
    """"Pro doesn't get telephony" is expressed as a disabled rate, not a
    special case in the calling code."""
    r = await rate_card.resolve_rate(db, "sms_outbound", plan_key="starter")
    assert r.is_enabled is False

    r2 = await rate_card.resolve_rate(db, "sms_outbound", plan_key="business")
    assert r2.is_enabled is True


@pytest.mark.normal
async def test_tenant_override_can_re_enable_a_disabled_plan(db: AsyncSession):
    """An agency on a normally-excluded plan can still be granted telephony."""
    await rate_card.upsert_rate(
        db, unit="sms_outbound", scope="tenant", scope_key="vip", is_enabled=True,
        sell_price_usd=0.02,
    )
    r = await rate_card.resolve_rate(
        db, "sms_outbound", tenant_key="vip", plan_key="starter"
    )
    assert r.is_enabled is True and r.source == "tenant"


@pytest.mark.normal
async def test_per_unit_markup_override(db: AsyncSession):
    await rate_card.upsert_rate(db, unit="voice_outbound_min", markup_multiplier=4.0)
    r = await rate_card.resolve_rate(db, "voice_outbound_min")
    assert r.sell_price_micros == int(round(r.our_cost_micros * 4.0))
    assert r.markup_applied == 4.0


@pytest.mark.normal
async def test_every_unit_resolves(db: AsyncSession):
    card = await rate_card.full_card(db)
    assert len(card) == len(rate_card.UNITS)
    assert all(row["sell_price_usd"] >= row["our_cost_usd"] for row in card)


@pytest.mark.normal
async def test_unknown_unit_is_rejected(db: AsyncSession):
    with pytest.raises(ValueError):
        await rate_card.resolve_rate(db, "not_a_real_unit")


# ---------------------------------------------------------------------------
# Prepaid credit
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_zero_balance_blocks_outbound(
    db: AsyncSession, admin_user: User, enforcement_on
):
    """Never front more than the tenant purchased — fraud AND collection
    protection in one mechanism."""
    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 0)

    with pytest.raises(telephony_credits.InsufficientTelephonyCredit) as exc:
        await telephony_credits.require_credit(
            db, admin_user, unit="sms_outbound", action="send a message"
        )
    assert exc.value.status_code == 402


@pytest.mark.critical
async def test_funded_balance_allows_outbound(
    db: AsyncSession, admin_user: User, enforcement_on
):
    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 10)
    await telephony_credits.require_credit(
        db, admin_user, unit="sms_outbound", action="send a message"
    )


@pytest.mark.critical
async def test_starter_plan_cannot_use_telephony_even_when_funded(
    db: AsyncSession, admin_user: User, enforcement_on
):
    """Plan gating is independent of balance."""
    await _set_plan(db, admin_user, "starter")
    await _fund(db, admin_user, 50)

    with pytest.raises(rate_card.TelephonyNotAvailable) as exc:
        await telephony_credits.require_credit(
            db, admin_user, unit="sms_outbound", action="send a message"
        )
    assert exc.value.status_code == 403


@pytest.mark.critical
async def test_charge_debits_and_records_both_numbers(
    db: AsyncSession, admin_user: User
):
    """Cost and billed on the same row is what makes margin a query."""
    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 10)
    rate = await rate_card.resolve_rate(db, "sms_outbound")

    entry = await telephony_credits.charge(
        db, row.tenant_key, unit="sms_outbound", quantity=100, rate=rate,
        external_ref="tw:test:sms:1",
    )
    assert entry is not None
    assert entry.billed_micros == rate.sell_price_micros * 100
    assert entry.our_cost_micros == rate.our_cost_micros * 100
    assert entry.billed_micros > entry.our_cost_micros

    balance = await telephony_credits.get_balance_micros(db, row.tenant_key)
    assert balance == 10 * MICROS_PER_USD - entry.billed_micros


@pytest.mark.critical
async def test_metering_is_idempotent(db: AsyncSession, admin_user: User):
    """Re-running the metering job must never double-bill the same usage."""
    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 10)
    rate = await rate_card.resolve_rate(db, "sms_outbound")

    first = await telephony_credits.charge(
        db, row.tenant_key, unit="sms_outbound", quantity=10, rate=rate,
        external_ref="tw:dup:sms:1",
    )
    after_first = await telephony_credits.get_balance_micros(db, row.tenant_key)

    second = await telephony_credits.charge(
        db, row.tenant_key, unit="sms_outbound", quantity=10, rate=rate,
        external_ref="tw:dup:sms:1",
    )
    assert first is not None
    assert second is None, "duplicate external_ref must be a no-op"
    assert await telephony_credits.get_balance_micros(db, row.tenant_key) == after_first


@pytest.mark.normal
async def test_topup_credits_balance_and_is_idempotent(
    db: AsyncSession, admin_user: User
):
    row = await telephony_credits.get_or_create(db, admin_user)
    await telephony_credits.apply_topup(
        db, row.tenant_key, 25 * MICROS_PER_USD, external_ref="cs_test_1"
    )
    assert await telephony_credits.get_balance_micros(db, row.tenant_key) == 25 * MICROS_PER_USD

    # Same Stripe session replayed — must not double-credit.
    again = await telephony_credits.apply_topup(
        db, row.tenant_key, 25 * MICROS_PER_USD, external_ref="cs_test_1"
    )
    assert again is None
    assert await telephony_credits.get_balance_micros(db, row.tenant_key) == 25 * MICROS_PER_USD


@pytest.mark.normal
async def test_topup_is_recorded_as_money_in(db: AsyncSession, admin_user: User):
    """Top-ups are negative billed_micros so they never inflate revenue."""
    row = await telephony_credits.get_or_create(db, admin_user)
    entry = await telephony_credits.apply_topup(
        db, row.tenant_key, 25 * MICROS_PER_USD, external_ref="cs_test_2"
    )
    assert entry.entry_type == "topup"
    assert entry.billed_micros < 0


@pytest.mark.normal
async def test_topup_amount_bounds(db: AsyncSession, admin_user: User):
    from app.core.exceptions import ValidationError

    class _S:
        stripe_secret_key = "sk_test_x"
        public_base_url = "https://example.com"

    with pytest.raises(ValidationError):
        await telephony_credits.create_topup_checkout(db, admin_user, 1.0, _S(), "")
    with pytest.raises(ValidationError):
        await telephony_credits.create_topup_checkout(db, admin_user, 10_000.0, _S(), "")


@pytest.mark.normal
async def test_balance_summary_flags_low_and_empty(db: AsyncSession, admin_user: User):
    await _fund(db, admin_user, 0.5)
    s = await telephony_credits.summary(db, admin_user)
    assert s["is_low"] is True and s["is_empty"] is False

    await _fund(db, admin_user, 0)
    s = await telephony_credits.summary(db, admin_user)
    assert s["is_empty"] is True


# ---------------------------------------------------------------------------
# Realised margin
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_margin_report_computes_realised_margin(
    db: AsyncSession, admin_user: User
):
    """The number that proves the markup works."""
    from app.billing.telephony_metering import margin_report

    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 50)
    rate = await rate_card.resolve_rate(db, "sms_outbound")

    await telephony_credits.charge(
        db, row.tenant_key, unit="sms_outbound", quantity=1000, rate=rate,
        external_ref="tw:margin:sms:1",
    )
    # A top-up must NOT be counted as revenue.
    await telephony_credits.apply_topup(
        db, row.tenant_key, 50 * MICROS_PER_USD, external_ref="cs_margin_1"
    )

    report = await margin_report(db)
    mine = [r for r in report if r["tenant_key"] == row.tenant_key]
    assert len(mine) == 1
    entry = mine[0]
    assert entry["billed_usd"] > entry["our_cost_usd"]
    assert entry["margin_usd"] == round(entry["billed_usd"] - entry["our_cost_usd"], 6)
    # Default 2.5x markup -> 60% margin.
    assert 55 <= entry["margin_pct"] <= 65


# ---------------------------------------------------------------------------
# A2P 10DLC
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_sms_locked_until_a2p_approved(
    db: AsyncSession, admin_user: User, enforcement_on
):
    """US carriers filter unregistered A2P traffic — fail closed."""
    from app.communication import a2p

    with pytest.raises(a2p.SmsNotRegistered) as exc:
        await a2p.require_sms_registered(db, admin_user)
    assert exc.value.status_code == 403

    reg = await a2p.get_or_create(db, admin_user)
    reg.status = "campaign_pending"
    await db.commit()
    with pytest.raises(a2p.SmsNotRegistered):
        await a2p.require_sms_registered(db, admin_user)

    reg.status = "approved"
    await db.commit()
    await a2p.require_sms_registered(db, admin_user)  # must not raise


@pytest.mark.normal
async def test_a2p_status_surfaces_a_waiting_state(db: AsyncSession, admin_user: User):
    """Carrier review takes 10-15 days; the tenant must see that, not a stall."""
    from app.communication import a2p

    reg = await a2p.get_or_create(db, admin_user)
    reg.status = "campaign_pending"
    await db.commit()

    s = await a2p.status_for(db, admin_user)
    assert s["is_pending"] is True
    assert s["sms_enabled"] is False
    assert a2p.TYPICAL_REVIEW_DAYS in s["typical_review_time"]
    assert s["next_step"]


@pytest.mark.normal
async def test_a2p_submission_requires_core_fields(db: AsyncSession, admin_user: User):
    from app.core.exceptions import ValidationError

    from app.communication import a2p

    with pytest.raises(ValidationError) as exc:
        await a2p.submit_registration(db, admin_user, {"business_name": "Acme"}, object())
    assert "Missing required fields" in exc.value.message


@pytest.mark.normal
async def test_a2p_fees_are_on_the_rate_card(db: AsyncSession):
    for unit in ("a2p_brand", "a2p_campaign", "a2p_campaign_monthly"):
        r = await rate_card.resolve_rate(db, unit, plan_key="business")
        assert r.our_cost_micros > 0
        assert r.sell_price_micros >= r.our_cost_micros


# ---------------------------------------------------------------------------
# Staged rollout — flags OFF (the state production deploys with)
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_flags_off_credit_gate_is_a_noop(db: AsyncSession, admin_user: User):
    """With telephony_enforce_credit off (the default), a zero-balance starter
    tenant is NOT blocked — deploying the rebilling stack changes nothing for
    existing users until the flag is flipped."""
    await _set_plan(db, admin_user, "starter")
    await _fund(db, admin_user, 0)
    # Must not raise, despite zero balance AND a plan whose rate card
    # disables telephony.
    await telephony_credits.require_credit(
        db, admin_user, unit="sms_outbound", action="send a message"
    )


@pytest.mark.critical
async def test_flags_off_a2p_gate_is_a_noop(db: AsyncSession, admin_user: User):
    """With telephony_enforce_a2p off (the default), unregistered tenants can
    still send — the hard carrier gate arrives only when the flag flips."""
    from app.communication import a2p

    await a2p.require_sms_registered(db, admin_user)  # must not raise


@pytest.mark.normal
async def test_flags_off_metering_still_records(db: AsyncSession, admin_user: User):
    """Staging gates the BLOCKING only. Usage is still metered, billed against
    the balance and written to the ledger from day one, so flipping the flag
    later starts from a true picture rather than a cold start."""
    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 5)
    rate = await rate_card.resolve_rate(db, "sms_outbound")

    entry = await telephony_credits.charge(
        db, row.tenant_key, unit="sms_outbound", quantity=10, rate=rate,
        external_ref="tw:staged:sms:1",
    )
    assert entry is not None
    assert entry.billed_micros > 0
    assert await telephony_credits.get_balance_micros(db, row.tenant_key) < 5 * MICROS_PER_USD
