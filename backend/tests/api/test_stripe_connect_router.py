"""Router-level tests for Stripe Connect account management.

Connect controls where a tenant's money goes, so /connect and /disconnect
are ADMIN-only (stricter than the ACCOUNTANT-or-ADMIN gate on issuing a
plain payment link). These pin the role gate and the /status response
shape rather than re-testing Stripe API mechanics (covered with mocked
stripe_lib calls in tests/integration/test_stripe_connect_account.py).
"""
import types

import pytest
from httpx import AsyncClient

from app.auth.models import User
from tests.conftest import auth_header


@pytest.mark.critical
async def test_status_is_null_for_a_fresh_user(client: AsyncClient, admin_user: User):
    resp = await client.get(
        "/api/integrations/stripe-connect/status", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.critical
async def test_status_requires_authentication(client: AsyncClient):
    resp = await client.get("/api/integrations/stripe-connect/status")
    assert resp.status_code == 401


@pytest.mark.critical
async def test_connect_rejects_non_admin(client: AsyncClient, accountant_user: User):
    resp = await client.get(
        "/api/integrations/stripe-connect/connect", headers=auth_header(accountant_user)
    )
    assert resp.status_code == 403


@pytest.mark.critical
async def test_disconnect_rejects_non_admin(client: AsyncClient, accountant_user: User):
    resp = await client.delete(
        "/api/integrations/stripe-connect/disconnect", headers=auth_header(accountant_user)
    )
    assert resp.status_code == 403


@pytest.mark.critical
async def test_connect_returns_onboarding_url_for_admin(
    client: AsyncClient, admin_user: User, monkeypatch
):
    from app.integrations.stripe_connect import service as connect_service
    from tests.conftest import TEST_SETTINGS

    monkeypatch.setattr(TEST_SETTINGS, "stripe_secret_key", "sk_test_x", raising=False)

    class _FakeAccount:
        id = "acct_test_router"

    class _FakeAccountLink:
        url = "https://connect.stripe.com/setup/e/acct_test_router/fake"

    monkeypatch.setattr(
        connect_service.stripe_lib,
        "Account",
        types.SimpleNamespace(create=lambda **kw: _FakeAccount()),
    )
    monkeypatch.setattr(
        connect_service.stripe_lib,
        "AccountLink",
        types.SimpleNamespace(create=lambda **kw: _FakeAccountLink()),
    )

    resp = await client.get(
        "/api/integrations/stripe-connect/connect", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["url"] == "https://connect.stripe.com/setup/e/acct_test_router/fake"


@pytest.mark.critical
async def test_disconnect_is_idempotent(client: AsyncClient, admin_user: User):
    # No connect account exists at all — disconnecting must not error.
    resp = await client.delete(
        "/api/integrations/stripe-connect/disconnect", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    resp = await client.delete(
        "/api/integrations/stripe-connect/disconnect", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
