"""Plaid Link gating (flag + MFA) and consent capture/persistence."""

import pytest
from sqlalchemy import func, select

from app.audit.models import AuditLog
from app.audit.service import AuditAction
from app.core import legal
from app.core.encryption import init_encryption_service
from app.integrations.plaid.models import PlaidConnection, PlaidConsent
from tests.conftest import TEST_SETTINGS, auth_header

# exchange_public_token encrypts the Plaid access token.
init_encryption_service(TEST_SETTINGS.fernet_key)


class _FakePlaid:
    def link_token_create(self, req):
        return {"link_token": "link-sandbox-abc"}

    def item_public_token_exchange(self, req):
        return {"access_token": "acc-123", "item_id": "item-1"}

    def accounts_get(self, req):
        return {
            "accounts": [
                {"account_id": "a1", "name": "Checking", "type": "depository",
                 "subtype": "checking", "mask": "1234"}
            ]
        }


@pytest.fixture()
def mock_plaid(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.plaid.service._get_plaid_client", lambda settings: _FakePlaid()
    )


async def _enable_mfa(db, user):
    user.mfa_enabled = True
    await db.commit()


# ---------------------------------------------------------------------------
# Gate: flag + MFA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_link_token_blocked_when_flag_off(client, app, admin_user, db, monkeypatch):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", False)
    await _enable_mfa(db, admin_user)
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 403
    assert r.json()["error"]["message"]["code"] == "PLAID_LINK_DISABLED"


@pytest.mark.asyncio
async def test_link_token_requires_mfa(client, app, admin_user, monkeypatch):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    # admin_user has no MFA enabled
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 403
    assert r.json()["error"]["message"]["code"] == "MFA_REQUIRED"


@pytest.mark.asyncio
async def test_link_token_succeeds_when_gated_open(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    await _enable_mfa(db, admin_user)
    r = await client.post("/api/integrations/plaid/link-token", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["link_token"] == "link-sandbox-abc"


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchange_without_consent_creates_nothing(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    await _enable_mfa(db, admin_user)

    r = await client.post(
        "/api/integrations/plaid/exchange-token",
        headers=auth_header(admin_user),
        json={
            "public_token": "public-abc",
            "institution_name": "Test Bank",
            "institution_id": "ins_1",
            "consent_acknowledged": False,
        },
    )
    assert r.status_code in (400, 422)

    conns = (await db.execute(select(func.count(PlaidConnection.id)))).scalar()
    consents = (await db.execute(select(func.count(PlaidConsent.id)))).scalar()
    assert conns == 0
    assert consents == 0


@pytest.mark.asyncio
async def test_exchange_with_consent_persists_both(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    await _enable_mfa(db, admin_user)

    r = await client.post(
        "/api/integrations/plaid/exchange-token",
        headers=auth_header(admin_user),
        json={
            "public_token": "public-abc",
            "institution_name": "Test Bank",
            "institution_id": "ins_1",
            "consent_acknowledged": True,
        },
    )
    assert r.status_code == 200, r.text

    conn = (await db.execute(select(PlaidConnection))).scalar_one()
    # Access token is stored ENCRYPTED, never in the clear.
    assert conn.encrypted_access_token != "acc-123"

    consent = (await db.execute(select(PlaidConsent))).scalar_one()
    assert consent.connection_id == conn.id
    assert consent.consent_version == legal.PLAID_CONSENT_VERSION
    assert consent.privacy_policy_version == legal.PRIVACY_POLICY_VERSION
    assert consent.consent_text == legal.PLAID_CONSENT_TEXT
    assert consent.product_scope == legal.PLAID_PRODUCT_SCOPE

    # Consent capture is auditable.
    actions = set(
        (await db.execute(select(AuditLog.action))).scalars().all()
    )
    assert AuditAction.PLAID_CONSENT_CAPTURED in actions
    assert AuditAction.PLAID_CONNECTION_CREATED in actions


@pytest.mark.asyncio
async def test_admin_can_list_consents(client, app, admin_user, db, monkeypatch, mock_plaid):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", True)
    await _enable_mfa(db, admin_user)
    await client.post(
        "/api/integrations/plaid/exchange-token",
        headers=auth_header(admin_user),
        json={
            "public_token": "public-abc",
            "institution_name": "Test Bank",
            "institution_id": "ins_1",
            "consent_acknowledged": True,
        },
    )

    r = await client.get("/api/integrations/plaid/admin/consents", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["consent_text"] == legal.PLAID_CONSENT_TEXT


@pytest.mark.asyncio
async def test_link_config_reports_gate_state(client, app, admin_user, monkeypatch):
    monkeypatch.setattr(app.state.settings, "plaid_link_enabled", False)
    r = await client.get("/api/integrations/plaid/link-config", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    cfg = r.json()["data"]
    assert cfg["enabled"] is False  # flag off -> button stays hidden
    assert cfg["consent_required"] is True
    assert cfg["mfa_required"] is True
    assert cfg["consent_version"] == legal.PLAID_CONSENT_VERSION
    assert cfg["privacy_policy_url"].endswith("/privacy")
