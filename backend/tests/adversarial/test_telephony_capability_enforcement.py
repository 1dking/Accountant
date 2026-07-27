"""Least-privilege capability enforcement (Step 0, final gate).

With telephony_enforce_capabilities ON, every billable telephony action is
gated on an operator-granted capability, checked BEFORE any subaccount is
created — so an ungranted tenant cannot self-provision by poking a billable
endpoint. Each denial has a test that proves the 403.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.billing.models import TelephonyAccount
from app.communication import service, telephony
from app.communication.models import TwilioPhoneNumber
from app.communication.telephony import CapabilityNotGranted, PlatformCircuitOpen
from app.contacts.models import Contact, ContactType
from app.core.encryption import get_encryption_service, init_encryption_service
from app.kyc.models import KycVerification  # noqa: F401 — register table for isolated runs
from tests.conftest import auth_header

init_encryption_service("")


@pytest.fixture(autouse=True)
def _enforce_on(app):
    """These tests assert enforcement BITES, so turn the flag on."""
    app.state.settings.telephony_enforce_capabilities = True
    yield
    app.state.settings.telephony_enforce_capabilities = False


async def _account(db, user, **grants) -> TelephonyAccount:
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


async def _contact(db, owner, phone: str):
    db.add(Contact(id=uuid.uuid4(), type=ContactType.CLIENT, company_name="Acme",
                   phone=phone, created_by=owner.id))
    await db.commit()


async def _tenant_account_count(db, user) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(TelephonyAccount).where(
            TelephonyAccount.tenant_key == telephony.tenant_key_for(user)
        )
    ) or 0)


# ===========================================================================
# THE critical property: no self-provisioning for an ungranted tenant
# ===========================================================================

@pytest.mark.critical
async def test_ungranted_tenant_is_denied_without_creating_a_subaccount(db, app, admin_user):
    """A tenant with NO subaccount hitting a billable action is refused, and NO
    subaccount is auto-created — the self-provisioning hole is closed."""
    assert await _tenant_account_count(db, admin_user) == 0

    with pytest.raises(CapabilityNotGranted):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")

    assert await _tenant_account_count(db, admin_user) == 0, "an ungranted tenant auto-provisioned"


@pytest.mark.critical
async def test_purchase_by_ungranted_tenant_is_403_and_provisions_nothing(client, db, app, admin_user, monkeypatch):
    """End to end: the purchase endpoint refuses an ungranted tenant with a 403
    and creates no subaccount."""
    monkeypatch.setattr(app.state.settings, "twilio_account_sid", "ACparent")
    monkeypatch.setattr(app.state.settings, "twilio_auth_token", "parent-tok")

    resp = await client.post(
        "/api/communication/twilio/purchase",
        headers=auth_header(admin_user),
        json={"phone_number": "+14155550000"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "TELEPHONY_CAPABILITY_NOT_GRANTED"
    assert await _tenant_account_count(db, admin_user) == 0


# ===========================================================================
# Per-capability denials (account exists, specific grant missing)
# ===========================================================================

@pytest.mark.critical
async def test_sms_denied_without_can_send_sms(db, app, admin_user):
    await _account(db, admin_user, allow_voice_outbound=True)  # voice yes, SMS no
    await _contact(db, admin_user, "+14155551234")
    with pytest.raises(CapabilityNotGranted):
        await service.send_sms(db, admin_user, "+14155551234", "hi", app.state.settings)


@pytest.mark.critical
async def test_voice_denied_without_can_make_calls(db, app, admin_user):
    await _account(db, admin_user, allow_sms=True)  # SMS yes, voice no
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = False
        telephony_enforce_capabilities = True
        twilio_account_sid = "ACparent"
        twilio_auth_token = "t"
        public_base_url = "https://x.test"

    await _contact(db, admin_user, "+14155551234")
    vr = await _voice_gate(db, admin_user.id, "+14155551234", _S())
    # _voice_gate returns TwiML rejection text (not None) when the gate refuses.
    assert vr is not None
    assert "enabled" in str(vr).lower() or "goodbye" in str(vr).lower()


@pytest.mark.critical
async def test_number_purchase_denied_without_can_buy_numbers(db, app, admin_user):
    await _account(db, admin_user, allow_sms=True, allow_voice_outbound=True)  # not number_purchase
    with pytest.raises(CapabilityNotGranted):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "number_purchase")


# ===========================================================================
# Granting works, and does NOT bypass the other gates
# ===========================================================================

@pytest.mark.critical
async def test_granted_capability_lets_the_action_proceed(db, app, admin_user, monkeypatch):
    """With the grant, enforce_billable_action returns the account (proceeds)."""
    acct = await _account(db, admin_user, allow_sms=True)

    async def _ok(_db, _s):
        return True

    monkeypatch.setattr(telephony, "platform_circuit_ok", _ok)
    resolved = await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")
    assert resolved.id == acct.id


@pytest.mark.critical
async def test_grant_does_not_bypass_circuit_breaker(db, app, admin_user, monkeypatch):
    """A granted capability is additive, not an override — the platform breaker
    still blocks."""
    await _account(db, admin_user, allow_number_purchase=True)

    async def _open(_db, _s):
        return False

    monkeypatch.setattr(telephony, "platform_circuit_ok", _open)
    with pytest.raises(PlatformCircuitOpen):
        await telephony.enforce_billable_action(db, admin_user, app.state.settings, "number_purchase")


# ===========================================================================
# No self-escalation: only an operator grants / provisions
# ===========================================================================

@pytest.mark.critical
async def test_tenant_cannot_grant_itself(client, db, team_member_user):
    acct = await _account(db, team_member_user)
    resp = await client.put(
        f"/api/integrations/sms/telephony/capabilities/{acct.tenant_key}",
        headers=auth_header(team_member_user),
        json={"allow_sms": True, "allow_number_purchase": True},
    )
    assert resp.status_code == 403
    await db.refresh(acct)
    assert acct.allow_sms is False and acct.allow_number_purchase is False


@pytest.mark.critical
async def test_provision_endpoint_is_operator_only(client, db, team_member_user, admin_user):
    """A tenant admin cannot provision a subaccount; the endpoint is operator-only.
    (admin_user here is a normal workspace admin, not a platform/operator admin.)"""
    resp = await client.post(
        "/api/platform-admin/telephony/accounts/provision",
        headers=auth_header(team_member_user),
        json={"user_id": str(team_member_user.id)},
    )
    assert resp.status_code in (401, 403)
    assert await _tenant_account_count(db, team_member_user) == 0


# ===========================================================================
# Gate 5 — purchase uses the tenant SUBACCOUNT, never the parent client
# ===========================================================================

@pytest.mark.critical
async def test_purchase_uses_subaccount_not_parent(client, db, app, admin_user, monkeypatch):
    """Isolation regression guard: a future change swapping subaccount_client for
    the parent client must fail this test."""
    acct = await _account(db, admin_user, allow_number_purchase=True)
    monkeypatch.setattr(app.state.settings, "twilio_account_sid", "ACparent")
    monkeypatch.setattr(app.state.settings, "twilio_auth_token", "parent-tok")

    seen = {}

    async def _circuit_ok(_db, _s):
        return True

    monkeypatch.setattr(telephony, "platform_circuit_ok", _circuit_ok)

    class _Purchased:
        sid = "PNsub123"
        phone_number = "+14155550000"
        friendly_name = "test"
        iso_country = "US"

    class _SubNumbers:
        def create(self, phone_number):
            seen["bought_on"] = "subaccount"
            return _Purchased()

    class _SubClient:
        incoming_phone_numbers = _SubNumbers()

    def _fake_sub_client(account):
        seen["sub_sid_used"] = account.subaccount_sid
        return _SubClient()

    class _ParentNumbers:
        def create(self, phone_number):
            seen["bought_on"] = "PARENT"  # must never happen
            return _Purchased()

    class _ParentClient:
        incoming_phone_numbers = _ParentNumbers()

    monkeypatch.setattr(telephony, "subaccount_client", _fake_sub_client)
    monkeypatch.setattr(telephony, "_parent_client", lambda s: _ParentClient())

    async def _noop_webhooks(settings, sid):
        return None

    monkeypatch.setattr(service, "configure_twilio_webhooks", _noop_webhooks)

    resp = await client.post(
        "/api/communication/twilio/purchase",
        headers=auth_header(admin_user),
        json={"phone_number": "+14155550000"},
    )
    assert resp.status_code in (200, 201), resp.text

    # Bought on the tenant's OWN subaccount, never the parent.
    assert seen.get("bought_on") == "subaccount", "number was NOT bought on the subaccount"
    assert seen.get("sub_sid_used") == acct.subaccount_sid

    row = (await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.tenant_key == acct.tenant_key)
    )).scalar_one()
    assert row.subaccount_sid == acct.subaccount_sid
