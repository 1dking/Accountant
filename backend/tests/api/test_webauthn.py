"""WebAuthn / passkey MFA — registration, assertion, sign-count replay,
either-factor Plaid gate, and TOTP-still-works.

The library's crypto verify functions are mocked (a real authenticator can't run
in CI); everything else — storage, sign-count replay, gate + login wiring — is
exercised for real."""

import types
import uuid

import pytest
import webauthn
from webauthn.helpers import bytes_to_base64url
from sqlalchemy import func, select

from app.auth.webauthn_models import WebAuthnCredential
from app.core.encryption import init_encryption_service
from tests.conftest import TEST_SETTINGS, auth_header

init_encryption_service(TEST_SETTINGS.fernet_key)

PASSWORD = "TestPass123!"
_FAKE_CRED_ID = b"\x11\x22\x33\x44\x55\x66"
_FAKE_CRED_ID_B64 = bytes_to_base64url(_FAKE_CRED_ID)


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    from app.auth import router as auth_router

    auth_router._login_attempts.clear()
    yield


@pytest.fixture()
def mock_attestation(monkeypatch):
    monkeypatch.setattr(
        webauthn, "verify_registration_response",
        lambda **kw: types.SimpleNamespace(
            credential_id=_FAKE_CRED_ID, credential_public_key=b"COSEKEY", sign_count=1, fmt="none"
        ),
    )


def _mock_assertion(monkeypatch, new_sign_count):
    monkeypatch.setattr(
        webauthn, "verify_authentication_response",
        lambda **kw: types.SimpleNamespace(new_sign_count=new_sign_count),
    )


async def _register_passkey(client, user, monkeypatch):
    """Drive register begin+finish for `user`, returning the stored credential."""
    monkeypatch.setattr(
        webauthn, "verify_registration_response",
        lambda **kw: types.SimpleNamespace(
            credential_id=_FAKE_CRED_ID, credential_public_key=b"COSEKEY", sign_count=1, fmt="none"
        ),
    )
    hdr = auth_header(user)
    b = await client.post("/api/auth/webauthn/register/begin", headers=hdr)
    assert b.status_code == 200, b.text
    f = await client.post(
        "/api/auth/webauthn/register/finish",
        headers=hdr,
        json={"credential": {"id": "abc", "response": {"transports": ["internal"]}},
              "device_name": "My Laptop"},
    )
    assert f.status_code == 200, f.text
    return f.json()["data"]


# ---------------------------------------------------------------------------
# Registration + management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_and_list_and_remove(client, admin_user, db, monkeypatch):
    data = await _register_passkey(client, admin_user, monkeypatch)
    assert data["device_name"] == "My Laptop"

    lst = await client.get("/api/auth/webauthn/credentials", headers=auth_header(admin_user))
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    # Stored public key only, never a private key.
    row = (await db.execute(select(WebAuthnCredential))).scalar_one()
    assert row.public_key == b"COSEKEY"
    assert row.credential_id == _FAKE_CRED_ID_B64

    rm = await client.delete(
        f"/api/auth/webauthn/credentials/{data['id']}", headers=auth_header(admin_user)
    )
    assert rm.status_code == 200
    assert (await db.execute(select(func.count(WebAuthnCredential.id)))).scalar() == 0


# ---------------------------------------------------------------------------
# Either factor = MFA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_passkey_only_user_counts_as_mfa(client, admin_user, db, monkeypatch):
    from app.auth.mfa_common import has_mfa

    assert await has_mfa(db, admin_user) is False  # no TOTP, no passkey yet
    await _register_passkey(client, admin_user, monkeypatch)
    await db.refresh(admin_user)
    assert await has_mfa(db, admin_user) is True  # passkey alone satisfies MFA


@pytest.mark.asyncio
async def test_totp_user_still_counts_as_mfa(db, team_member_user):
    """Regression: a TOTP-only user (no passkey) must still be MFA-enabled."""
    from app.auth.mfa_common import has_mfa

    team_member_user.mfa_enabled = True
    await db.commit()
    assert await has_mfa(db, team_member_user) is True


# ---------------------------------------------------------------------------
# Plaid gate accepts EITHER factor
# ---------------------------------------------------------------------------

class _FakePlaid:
    def link_token_create(self, req):
        return {"link_token": "link-abc"}


@pytest.fixture()
def mock_plaid(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.plaid.service._get_plaid_client", lambda settings: _FakePlaid()
    )


@pytest.mark.asyncio
async def test_plaid_gate_accepts_passkey(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    # No TOTP — only a passkey.
    await _register_passkey(client, admin_user, monkeypatch)
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["link_token"] == "link-abc"


@pytest.mark.asyncio
async def test_plaid_gate_accepts_totp(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    admin_user.mfa_enabled = True  # TOTP only, no passkey
    await db.commit()
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_plaid_gate_blocks_no_factor(client, app, admin_user, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 403
    assert r.json()["error"]["message"]["code"] == "MFA_REQUIRED"


# ---------------------------------------------------------------------------
# Login via passkey + sign-count replay rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_passkey_login_and_replay_rejection(client, team_member_user, db, monkeypatch):
    await _register_passkey(client, team_member_user, monkeypatch)

    # Password login now returns a challenge listing webauthn as a method.
    login = await client.post(
        "/api/auth/login", json={"email": team_member_user.email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    body = login.json()["data"]
    assert body["mfa_required"] is True
    assert "webauthn" in body["methods"]
    mfa_token = body["mfa_token"]

    # Begin assertion (sets the challenge).
    b = await client.post("/api/auth/webauthn/login/begin", json={"mfa_token": mfa_token})
    assert b.status_code == 200, b.text

    # A non-increasing sign count (stored=1) must be rejected as a possible clone.
    _mock_assertion(monkeypatch, new_sign_count=1)
    replay = await client.post(
        "/api/auth/webauthn/login/verify",
        json={"mfa_token": mfa_token, "credential": {"id": _FAKE_CRED_ID_B64}},
    )
    assert replay.status_code in (400, 422)

    # A fresh begin + an increasing sign count succeeds and returns real tokens.
    await client.post("/api/auth/webauthn/login/begin", json={"mfa_token": mfa_token})
    _mock_assertion(monkeypatch, new_sign_count=2)
    ok = await client.post(
        "/api/auth/webauthn/login/verify",
        json={"mfa_token": mfa_token, "credential": {"id": _FAKE_CRED_ID_B64}},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["access_token"]

    # Sign count advanced to 2 in storage.
    row = (await db.execute(select(WebAuthnCredential))).scalar_one()
    assert row.sign_count == 2
