"""A second factor is required to READ consumer financial data — and it can
NEVER lock anyone out of the application.

The lockout-safety tests are the point of this file, not an afterthought: an
earlier MFA change did lock the owner out of production, so the guarantees are
encoded here as assertions rather than left as intentions.
"""

import uuid

import pytest

from app.auth.webauthn_models import WebAuthnCredential
from app.core.encryption import init_encryption_service
from tests.conftest import TEST_SETTINGS, auth_header

init_encryption_service(TEST_SETTINGS.fernet_key)

PASSWORD = "TestPass123!"

DATA_ENDPOINTS = [
    ("get", "/api/integrations/plaid/connections"),
    ("get", "/api/integrations/plaid/transactions"),
]


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    from app.auth import router as auth_router

    auth_router._login_attempts.clear()
    yield


# ---------------------------------------------------------------------------
# The gate itself
# ---------------------------------------------------------------------------

@pytest.mark.critical
@pytest.mark.parametrize("method,path", DATA_ENDPOINTS)
async def test_no_second_factor_cannot_read_financial_data(client, admin_user, method, path):
    resp = await getattr(client, method)(path, headers=auth_header(admin_user))
    assert resp.status_code == 403, f"{path} served financial data without MFA"
    assert resp.json()["error"]["message"]["code"] == "MFA_REQUIRED"


@pytest.mark.critical
@pytest.mark.parametrize("method,path", DATA_ENDPOINTS)
async def test_authenticator_app_satisfies_the_gate(client, admin_user, db, method, path):
    admin_user.mfa_enabled = True  # TOTP enrolled
    await db.commit()
    resp = await getattr(client, method)(path, headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text


@pytest.mark.critical
@pytest.mark.parametrize("method,path", DATA_ENDPOINTS)
async def test_passkey_satisfies_the_gate(client, admin_user, db, method, path):
    """Either factor works — a passkey alone is enough, no TOTP required."""
    db.add(WebAuthnCredential(
        user_id=admin_user.id,
        credential_id=f"cred-{uuid.uuid4().hex}",
        public_key=b"PK",
        sign_count=0,
        device_name="Phone",
    ))
    await db.commit()
    resp = await getattr(client, method)(path, headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text


@pytest.mark.critical
async def test_kill_switch_lifts_the_gate(client, app, admin_user, monkeypatch):
    """PLAID_REQUIRE_MFA_FOR_DATA=false must restore access without a code change."""
    monkeypatch.setattr(app.state.settings, "plaid_require_mfa_for_data", False)
    resp = await client.get(
        "/api/integrations/plaid/connections", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# LOCKOUT SAFETY — the guarantees that matter most
# ---------------------------------------------------------------------------

@pytest.mark.critical
async def test_login_still_works_without_any_second_factor(client, admin_user):
    """The gate must NOT touch authentication. An account with no MFA signs in
    normally and receives real tokens."""
    resp = await client.post(
        "/api/auth/login", json={"email": admin_user.email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body.get("access_token"), "login stopped issuing tokens — lockout risk"
    assert not body.get("mfa_required"), "gate leaked into the login flow"


@pytest.mark.critical
async def test_rest_of_the_app_is_unaffected_without_mfa(client, admin_user):
    """Only Plaid data is gated. Everything else stays reachable, so nobody is
    shut out of their own account."""
    for path in ("/api/auth/me", "/api/contacts", "/api/cashbook/entries", "/api/tasks"):
        resp = await client.get(path, headers=auth_header(admin_user))
        assert resp.status_code == 200, f"{path} broke for an account without MFA"


@pytest.mark.critical
async def test_enrollment_path_stays_reachable_without_mfa(client, admin_user):
    """The UI must still be able to tell the user HOW to fix it: link-config and
    the passkey/TOTP enrollment endpoints cannot themselves require MFA."""
    cfg = await client.get(
        "/api/integrations/plaid/link-config", headers=auth_header(admin_user)
    )
    assert cfg.status_code == 200, "link-config gated — UI could not prompt enrollment"
    assert cfg.json()["data"]["mfa_satisfied"] is False

    status_resp = await client.get("/api/auth/mfa/status", headers=auth_header(admin_user))
    assert status_resp.status_code == 200

    begin = await client.post("/api/auth/mfa/enroll", headers=auth_header(admin_user))
    assert begin.status_code == 200, "could not start MFA enrollment without MFA"
