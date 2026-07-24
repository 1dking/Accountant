"""Tests for account subscription billing (the customer paying for their plan).

Covers the auth gate, get-or-create of the default Starter subscription, the
free-tier switch (no Stripe needed), the "Stripe not configured" guard on paid
plans, plan validation, and the webhook lifecycle handler.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing import service
from app.platform_admin.models import PlatformSetting
from tests.conftest import auth_header

SUBSCRIPTION_URL = "/api/billing/subscription"
CHECKOUT_URL = "/api/billing/checkout"


async def _seed_pricing(db: AsyncSession) -> None:
    db.add_all([
        PlatformSetting(key="plan_pro_price", value="49", category="pricing"),
        PlatformSetting(key="plan_pro_annual_price", value="470", category="pricing"),
        PlatformSetting(key="plan_starter_price", value="0", category="pricing"),
    ])
    await db.commit()


# ---------------------------------------------------------------------------
# Auth + defaults
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_subscription_requires_auth(client: AsyncClient):
    resp = await client.get(SUBSCRIPTION_URL)
    assert resp.status_code == 401, resp.text


@pytest.mark.critical
async def test_subscription_defaults_to_starter(client: AsyncClient, admin_user: User):
    """A user with no subscription row gets a Starter one created on read."""
    resp = await client.get(SUBSCRIPTION_URL, headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["plan_key"] == "starter"
    assert data["status"] == "active"
    assert data["has_stripe_customer"] is False


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_checkout_free_plan_switches_without_stripe(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """Choosing the Starter (free) plan flips the plan server-side and returns
    no Stripe redirect."""
    await _seed_pricing(db)
    resp = await client.post(
        CHECKOUT_URL,
        json={"plan_key": "starter", "period": "monthly"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["free"] is True
    assert data["plan_key"] == "starter"


@pytest.mark.normal
async def test_checkout_paid_plan_without_stripe_configured_errors(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """A paid plan with no Stripe key returns a validation error rather than a
    Stripe crash. TEST_SETTINGS has no stripe_secret_key."""
    await _seed_pricing(db)
    resp = await client.post(
        CHECKOUT_URL,
        json={"plan_key": "pro", "period": "monthly"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.critical
async def test_annual_charges_twelve_times_the_monthly_rate():
    """Annual settings are stored as '$/mo billed yearly', so a yearly interval
    must bill 12x that rate — not the per-month figure once a year."""
    assert service._charge_amount(23.0, "annual") == 276.0
    assert service._charge_amount(23.0, "monthly") == 23.0


@pytest.mark.critical
async def test_checkout_paid_plan_with_zero_price_is_rejected(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """A paid plan priced at $0 is a misconfiguration — it must NOT silently
    hand out the plan for free."""
    db.add(PlatformSetting(key="plan_pro_price", value="0", category="pricing"))
    await db.commit()

    resp = await client.post(
        CHECKOUT_URL,
        json={"plan_key": "pro", "period": "monthly"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, resp.text
    assert "not configured" in resp.text.lower()

    # And the account must still be on Starter, not silently upgraded.
    sub = await service.get_subscription(db, admin_user)
    assert sub.plan_key == "starter"


@pytest.mark.critical
async def test_checkout_rejects_incoherent_annual_pricing(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """If the annual per-month rate isn't cheaper than monthly, refuse rather
    than lock someone into an overpriced yearly commitment."""
    db.add_all([
        PlatformSetting(key="plan_pro_price", value="29", category="pricing"),
        PlatformSetting(key="plan_pro_annual_price", value="164", category="pricing"),
    ])
    await db.commit()

    resp = await client.post(
        CHECKOUT_URL,
        json={"plan_key": "pro", "period": "annual"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, resp.text
    assert "misconfigured" in resp.text.lower()


@pytest.mark.normal
async def test_checkout_unknown_plan_rejected(
    client: AsyncClient, admin_user: User
):
    resp = await client.post(
        CHECKOUT_URL,
        json={"plan_key": "platinum", "period": "monthly"},
        headers=auth_header(admin_user),
    )
    # Service rejects an unknown plan_key with a ValidationError (422).
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Webhook lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_webhook_subscription_deleted_downgrades_to_starter(
    db: AsyncSession, admin_user: User
):
    """A customer.subscription.deleted event drops the account back to Starter."""
    sub = await service.get_subscription(db, admin_user)
    sub.plan_key = "pro"
    sub.status = "active"
    sub.stripe_subscription_id = "sub_test123"
    await db.commit()

    await service.handle_stripe_event(
        db, "customer.subscription.deleted", {"id": "sub_test123"}
    )

    refreshed = await service.get_subscription(db, admin_user)
    assert refreshed.plan_key == "starter"
    assert refreshed.status == "canceled"
    assert refreshed.stripe_subscription_id is None


@pytest.mark.critical
async def test_period_end_read_from_subscription_item():
    """Newer Stripe API versions dropped the top-level current_period_end and
    put it on the subscription item — read both shapes or the renewal date
    silently stays blank."""
    # Modern shape: item-level only.
    assert service._period_end(
        {"id": "sub_1", "items": {"data": [{"current_period_end": 1787590096}]}}
    ) == 1787590096
    # Legacy shape: top level.
    assert service._period_end({"id": "sub_1", "current_period_end": 123}) == 123
    # Neither present.
    assert service._period_end({"id": "sub_1", "items": {"data": [{}]}}) is None
    assert service._period_end(None) is None


@pytest.mark.normal
async def test_webhook_ignores_non_subscription_events(
    db: AsyncSession, admin_user: User
):
    """An event whose metadata isn't kind=account_subscription is a no-op."""
    sub = await service.get_subscription(db, admin_user)
    assert sub.plan_key == "starter"

    # A proposal-payment checkout completing must not touch the subscription.
    await service.handle_stripe_event(
        db,
        "checkout.session.completed",
        {"metadata": {"kind": "proposal_payment"}, "subscription": None},
    )

    refreshed = await service.get_subscription(db, admin_user)
    assert refreshed.plan_key == "starter"


@pytest.mark.normal
async def test_webhook_updated_unknown_subscription_is_noop(db: AsyncSession):
    """An update for a Stripe subscription we don't track is silently ignored."""
    await service.handle_stripe_event(
        db,
        "customer.subscription.updated",
        {"id": f"sub_{uuid.uuid4().hex}", "status": "active"},
    )
