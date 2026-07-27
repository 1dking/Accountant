"""Step 0 telephony safety gates + Step 2 least-privilege capabilities.

These guard real money and fraud exposure, so each gate gets a test that proves
it REFUSES, not merely that the happy path works.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.billing.models import TelephonyAccount
from app.communication import telephony
from app.communication.telephony import (
    CAPABILITIES,
    CapabilityNotGranted,
    PlatformCircuitOpen,
    TelephonySuspended,
)
from app.core.encryption import init_encryption_service
from tests.conftest import auth_header

init_encryption_service("")


@pytest.fixture(autouse=True)
def _enforce_capabilities(app):
    """Capability enforcement ships staged behind a flag (prod has legacy numbers
    on the parent account). These tests assert the gate BITES, so turn it on."""
    app.state.settings.telephony_enforce_capabilities = True
    yield
    app.state.settings.telephony_enforce_capabilities = False


async def _account(db, user, **grants) -> TelephonyAccount:
    """A tenant subaccount. Grants default OFF unless explicitly passed.

    Uses the REAL tenant key for the user so ensure_account() resolves this row
    instead of trying to provision a new subaccount at Twilio.
    """
    from app.core.encryption import get_encryption_service

    acct = TelephonyAccount(
        tenant_key=telephony.tenant_key_for(user),
        owner_user_id=user.id,
        subaccount_sid=f"AC{uuid.uuid4().hex}",
        encrypted_auth_token=get_encryption_service().encrypt("tok"),
        status="active",
        **grants,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


# ---------------------------------------------------------------------------
# Step 2 — least privilege
# ---------------------------------------------------------------------------

@pytest.mark.critical
async def test_new_subaccount_grants_nothing_by_default(db, admin_user):
    """A provisioned subaccount must start with EVERY capability off."""
    acct = await _account(db, admin_user)
    for name in CAPABILITIES:
        assert telephony.has_capability(acct, name) is False, f"{name} was on by default"


@pytest.mark.critical
async def test_require_capability_refuses_ungranted(db, admin_user):
    acct = await _account(db, admin_user, allow_sms=True)
    telephony.require_capability(acct, "sms")  # granted -> passes
    for denied in ("voice_outbound", "mms", "number_purchase"):
        with pytest.raises(CapabilityNotGranted):
            telephony.require_capability(acct, denied)


@pytest.mark.critical
async def test_unknown_capability_denies_rather_than_defaults_on(db, admin_user):
    """Fail closed: a typo'd capability name must never open a billable path."""
    acct = await _account(db, admin_user, allow_sms=True, allow_voice_outbound=True)
    assert telephony.has_capability(acct, "sms_outbund") is False
    with pytest.raises(CapabilityNotGranted):
        telephony.require_capability(acct, "totally_made_up")


@pytest.mark.critical
async def test_granting_one_capability_does_not_grant_others(db, admin_user):
    """Voice yes / SMS no must be expressible, and stay that way."""
    acct = await _account(db, admin_user, allow_voice_outbound=True)
    assert telephony.has_capability(acct, "voice_outbound") is True
    assert telephony.has_capability(acct, "sms") is False
    assert telephony.has_capability(acct, "number_purchase") is False


# ---------------------------------------------------------------------------
# The combined choke point
# ---------------------------------------------------------------------------

@pytest.mark.critical
async def test_enforce_billable_action_blocks_ungranted_capability(db, app, admin_user):
    await _account(db, admin_user)  # no grants
    with pytest.raises(CapabilityNotGranted):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")


@pytest.mark.critical
async def test_enforce_billable_action_blocks_when_suspended(db, app, admin_user):
    """The kill switch is inherited: a suspended tenant cannot spend."""
    acct = await _account(db, admin_user, allow_sms=True)
    acct.status = "suspended"
    acct.suspended_reason = "monthly cap breached"
    await db.commit()

    with pytest.raises(TelephonySuspended):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")


@pytest.mark.critical
async def test_platform_circuit_breaker_blocks_spending(db, app, admin_user, monkeypatch):
    """Aggregate ceiling must stop an EXISTING tenant, not just new provisioning."""
    await _account(db, admin_user, allow_sms=True)

    async def _tripped(_db, _settings):
        return False

    monkeypatch.setattr(telephony, "platform_circuit_ok", _tripped)
    with pytest.raises(PlatformCircuitOpen):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.critical
async def test_capabilities_are_per_tenant(db, admin_user, team_member_user):
    """One tenant's grants must not leak to another."""
    a = await _account(db, admin_user, allow_sms=True, allow_voice_outbound=True)
    b = await _account(db, team_member_user)

    assert telephony.has_capability(a, "sms") is True
    assert telephony.has_capability(b, "sms") is False
    assert a.subaccount_sid != b.subaccount_sid
    assert a.tenant_key != b.tenant_key


@pytest.mark.critical
async def test_tenant_cannot_grant_itself_capabilities(client, db, team_member_user, admin_user):
    """Only an operator may write the grants; the endpoint is platform-admin only."""
    acct = await _account(db, team_member_user)

    denied = await client.put(
        f"/api/integrations/sms/telephony/capabilities/{acct.tenant_key}",
        headers=auth_header(team_member_user),
        json={"allow_sms": True, "allow_number_purchase": True},
    )
    assert denied.status_code == 403, "a tenant escalated its own capabilities"

    await db.refresh(acct)
    assert acct.allow_sms is False
    assert acct.allow_number_purchase is False


@pytest.mark.critical
async def test_operator_can_grant_and_revoke(client, db, team_member_user, admin_user):
    acct = await _account(db, team_member_user)

    granted = await client.put(
        f"/api/integrations/sms/telephony/capabilities/{acct.tenant_key}",
        headers=auth_header(admin_user),
        json={"allow_sms": True},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["data"]["capabilities"]["sms"] is True
    assert granted.json()["data"]["capabilities"]["voice_outbound"] is False

    await db.refresh(acct)
    assert acct.allow_sms is True
    assert acct.capabilities_updated_by == admin_user.id

    revoked = await client.put(
        f"/api/integrations/sms/telephony/capabilities/{acct.tenant_key}",
        headers=auth_header(admin_user),
        json={"allow_sms": False},
    )
    assert revoked.json()["data"]["capabilities"]["sms"] is False


# ---------------------------------------------------------------------------
# SMS Pumping Protection
# ---------------------------------------------------------------------------

def test_pumping_protection_enables_risk_check_on_every_service():
    """It must actually set the flag, and report per-service results."""
    updated: list[bool] = []

    class _Svc:
        def update(self, **kw):
            updated.append(kw.get("sms_pumping_risk_check_enabled"))

    class _Client:
        class messaging:
            class v1:
                class services:
                    @staticmethod
                    def list(limit=100):
                        return [_Svc(), _Svc()]

    out = telephony.apply_sms_pumping_protection(_Client(), "test-acct")
    assert updated == [True, True]
    assert "2/2" in out["pumping_protection"]


def test_pumping_protection_survives_an_api_failure():
    """A Twilio error must be reported, not raised into the provisioning path."""

    class _Client:
        class messaging:
            class v1:
                class services:
                    @staticmethod
                    def list(limit=100):
                        raise RuntimeError("twilio unavailable")

    out = telephony.apply_sms_pumping_protection(_Client(), "test-acct")
    assert out["pumping_protection"].startswith("FAILED")


@pytest.mark.critical
async def test_staging_flag_off_allows_but_warns(db, app, admin_user, monkeypatch):
    """With the flag OFF the gate must NOT refuse — that is what makes this safe
    to deploy while 2 legacy numbers still live on the parent account."""
    monkeypatch.setattr(app.state.settings, "telephony_enforce_capabilities", False)
    await _account(db, admin_user)  # no grants at all
    acct = await telephony.enforce_billable_action(
        db, admin_user, app.state.settings, "sms"
    )
    assert acct is not None  # allowed, logged as a staging warning
