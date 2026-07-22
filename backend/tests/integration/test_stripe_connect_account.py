"""Stripe Connect (Express) — per-tenant payment routing.

Each agency using this product can connect their own Stripe account so their
clients' invoice/proposal payments land in the agency's own balance instead
of the platform's. `get_active_connect_account_id` is the single seam every
payment call site goes through to decide "use this tenant's connected
account" vs "fall back to the platform's own key" — these tests pin that
seam's behavior, the account.updated onboarding-status sync, the fallback
path when no connect account exists, and the cross-tenant webhook guard
that stops one tenant's Connect event from touching another tenant's
invoice.
"""
import types
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from app.auth.models import User
from app.integrations.stripe_connect.models import StripeConnectAccount
from app.integrations.stripe_connect.service import (
    _apply_account_fields,
    get_active_connect_account_id,
    get_connect_account_for_user,
)
from app.invoicing.models import Invoice, InvoiceStatus


async def _connect_account(db, user_id, **overrides) -> StripeConnectAccount:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=user_id,
        stripe_account_id=f"acct_{uuid.uuid4().hex[:16]}",
        charges_enabled=True,
        payouts_enabled=True,
        details_submitted=True,
        is_active=True,
    )
    defaults.update(overrides)
    row = StripeConnectAccount(**defaults)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# get_active_connect_account_id — the fallback seam
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_no_connect_account_returns_none(db, admin_user: User):
    assert await get_active_connect_account_id(db, admin_user.id) is None


@pytest.mark.critical
async def test_not_yet_chargeable_returns_none(db, admin_user: User):
    await _connect_account(db, admin_user.id, charges_enabled=False)
    assert await get_active_connect_account_id(db, admin_user.id) is None


@pytest.mark.critical
async def test_disconnected_account_returns_none(db, admin_user: User):
    await _connect_account(db, admin_user.id, is_active=False)
    assert await get_active_connect_account_id(db, admin_user.id) is None


@pytest.mark.critical
async def test_active_chargeable_account_returns_its_id(db, admin_user: User):
    account = await _connect_account(db, admin_user.id)
    assert await get_active_connect_account_id(db, admin_user.id) == account.stripe_account_id


# ---------------------------------------------------------------------------
# account.updated — the authoritative "fully onboarded" signal
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_account_updated_flips_charges_enabled_and_stamps_once(db, admin_user: User):
    account = await _connect_account(db, admin_user.id, charges_enabled=False, details_submitted=False)

    fake_account = {"charges_enabled": True, "payouts_enabled": True, "details_submitted": True}
    await _apply_account_fields(db, account, fake_account)
    await db.refresh(account)

    assert account.charges_enabled is True
    assert account.onboarding_completed_at is not None
    first_stamp = account.onboarding_completed_at

    # A second account.updated (e.g. payouts toggling) must not re-stamp.
    await _apply_account_fields(db, account, fake_account)
    await db.refresh(account)
    assert account.onboarding_completed_at == first_stamp


# ---------------------------------------------------------------------------
# Fallback path — no connect account means unchanged, platform-key behavior
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_checkout_session_omits_stripe_account_without_a_connect_row(
    db, admin_user: User, sample_invoice: Invoice, monkeypatch
):
    from app.integrations.stripe import service as stripe_service
    from tests.conftest import TEST_SETTINGS

    monkeypatch.setattr(TEST_SETTINGS, "stripe_secret_key", "sk_test_x", raising=False)

    captured = {}

    class _FakeSession:
        id = "cs_test_fallback"
        url = "https://checkout.stripe.com/pay/cs_test_fallback"

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeSession()

    monkeypatch.setattr(stripe_service.stripe_lib.checkout, "Session", types.SimpleNamespace(create=_fake_create))

    await stripe_service.create_checkout_session(db, sample_invoice.id, admin_user, TEST_SETTINGS)

    assert "stripe_account" not in captured


@pytest.mark.critical
async def test_checkout_session_passes_stripe_account_when_connected(
    db, admin_user: User, sample_invoice: Invoice, monkeypatch
):
    from app.integrations.stripe import service as stripe_service
    from tests.conftest import TEST_SETTINGS

    monkeypatch.setattr(TEST_SETTINGS, "stripe_secret_key", "sk_test_x", raising=False)
    account = await _connect_account(db, admin_user.id)

    captured = {}

    class _FakeSession:
        id = "cs_test_connected"
        url = "https://checkout.stripe.com/pay/cs_test_connected"

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeSession()

    monkeypatch.setattr(stripe_service.stripe_lib.checkout, "Session", types.SimpleNamespace(create=_fake_create))

    await stripe_service.create_checkout_session(db, sample_invoice.id, admin_user, TEST_SETTINGS)

    assert captured.get("stripe_account") == account.stripe_account_id


# ---------------------------------------------------------------------------
# Cross-tenant webhook guard
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def other_admin(db):
    from app.auth.models import Role
    from app.auth.utils import hash_password

    user = User(
        id=uuid.uuid4(),
        email="other-admin@test.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.critical
async def test_webhook_rejects_mismatched_connect_account(
    db, admin_user: User, other_admin: User, sample_invoice: Invoice
):
    """A checkout.session.completed carrying someone ELSE's connected account
    id must not be allowed to mark this invoice paid — otherwise one
    tenant's Stripe events could pay another tenant's invoices."""
    from app.integrations.stripe.service import _handle_checkout_completed

    # sample_invoice is owned by admin_user, which has its own connect account.
    await _connect_account(db, admin_user.id, stripe_account_id="acct_owner")
    # The event claims to come from a DIFFERENT connected account.
    await _connect_account(db, other_admin.id, stripe_account_id="acct_attacker")

    fake_session = {
        "id": "cs_test_mismatch",
        "amount_total": int(sample_invoice.total * 100),
        "payment_intent": "pi_test_mismatch",
        "metadata": {"invoice_id": str(sample_invoice.id)},
    }

    await _handle_checkout_completed(db, fake_session, expected_connect_account_id="acct_attacker")

    await db.refresh(sample_invoice)
    assert sample_invoice.status != InvoiceStatus.PAID


@pytest.mark.critical
async def test_webhook_accepts_matching_connect_account(
    db, admin_user: User, sample_invoice: Invoice
):
    from app.integrations.stripe.service import _handle_checkout_completed

    account = await _connect_account(db, admin_user.id)

    fake_session = {
        "id": "cs_test_match",
        "amount_total": int(sample_invoice.total * 100),
        "payment_intent": "pi_test_match",
        "metadata": {"invoice_id": str(sample_invoice.id)},
    }

    await _handle_checkout_completed(db, fake_session, expected_connect_account_id=account.stripe_account_id)

    await db.refresh(sample_invoice)
    assert sample_invoice.status == InvoiceStatus.PAID


@pytest.mark.critical
async def test_platform_webhook_path_is_unaffected(
    db, admin_user: User, sample_invoice: Invoice
):
    """The existing platform webhook always passes expected_connect_account_id=None,
    which must skip the guard entirely — unchanged single-tenant behavior."""
    from app.integrations.stripe.service import _handle_checkout_completed

    fake_session = {
        "id": "cs_test_platform",
        "amount_total": int(sample_invoice.total * 100),
        "payment_intent": "pi_test_platform",
        "metadata": {"invoice_id": str(sample_invoice.id)},
    }

    await _handle_checkout_completed(db, fake_session)  # expected_connect_account_id defaults to None

    await db.refresh(sample_invoice)
    assert sample_invoice.status == InvoiceStatus.PAID
