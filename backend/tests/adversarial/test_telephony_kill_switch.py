"""GAP 1 (usage-trigger kill switch + signature validation) and GAP 2 (platform
circuit breaker on the outbound + purchase paths).

These are fraud kill switches guarding real money, so every gate has a test that
proves it FIRES — a valid trigger suspends, a spoofed one does not, and an
over-ceiling send/purchase is refused.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from twilio.request_validator import RequestValidator

from app.audit.models import AuditLog
from app.billing.models import (
    MICROS_PER_USD,
    TelephonyAccount,
    TelephonyLedgerEntry,
)
from app.communication import service, telephony
from app.communication.models import TwilioPhoneNumber
from app.communication.telephony import (
    PlatformCircuitOpen,
    TelephonyCapReached,
    TelephonySuspended,
)
from app.contacts.models import Contact, ContactType
from app.core.encryption import get_encryption_service, init_encryption_service
# Registers kyc_verifications so create_all builds it when this file runs in
# isolation — the purchase endpoint SELECTs it (router.py:1329) before the
# circuit breaker, so without this the proof 500s on a missing table instead of
# exercising the gate. Not a code change; just makes the proof reliable alone.
from app.kyc.models import KycVerification  # noqa: F401
from tests.conftest import auth_header

init_encryption_service("")

TRIGGER_PATH = "/api/integrations/sms/usage-trigger"
# The test client uses base_url http://test, and there are no forwarding
# headers, so this is exactly the URL the webhook reconstructs and Twilio would
# have signed.
TRIGGER_URL = "http://test" + TRIGGER_PATH
SUB_TOKEN = "tok"  # the plaintext auth token _account() encrypts


def _sign(token: str, params: dict) -> dict:
    """Header dict with a genuine Twilio signature for these params + URL."""
    return {"X-Twilio-Signature": RequestValidator(token).compute_signature(TRIGGER_URL, params)}


async def _account(db, user, *, status="active", token=SUB_TOKEN, **grants) -> TelephonyAccount:
    acct = TelephonyAccount(
        tenant_key=telephony.tenant_key_for(user),
        owner_user_id=user.id,
        subaccount_sid=f"AC{uuid.uuid4().hex}",
        encrypted_auth_token=get_encryption_service().encrypt(token),
        status=status,
        **grants,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


async def _contact(db, owner, phone: str) -> Contact:
    c = Contact(
        id=uuid.uuid4(), type=ContactType.CLIENT, company_name="Acme",
        phone=phone, created_by=owner.id,
    )
    db.add(c)
    await db.commit()
    return c


async def _audit_rows(db, action: str) -> list[AuditLog]:
    return list((await db.execute(select(AuditLog).where(AuditLog.action == action))).scalars())


def _stub_parent_ok(_settings):
    """A parent Twilio client whose account status update is a no-op."""
    class _Acc:
        def update(self, **kw):
            return None

    class _Api:
        def accounts(self, sid):
            return _Acc()

    class _Client:
        api = _Api()

    return _Client()


async def _circuit_open(monkeypatch):
    async def _false(_db, _settings):
        return False

    monkeypatch.setattr(telephony, "platform_circuit_ok", _false)


# ===========================================================================
# GAP 1 — the usage-trigger kill switch + signature validation
# ===========================================================================

@pytest.mark.critical
async def test_signed_monthly_breach_suspends_and_writes_audit(client, db, admin_user, monkeypatch):
    """A genuinely-signed monthly breach suspends the subaccount AND records an
    audit row naming the system actor — the whole point of the kill switch."""
    acct = await _account(db, admin_user)
    # suspend() would call the parent Twilio client; stub it so no network.
    monkeypatch.setattr(telephony, "_parent_client", _stub_parent_ok)

    params = {
        "AccountSid": acct.subaccount_sid,
        "FriendlyName": "obrain-monthly-spend",
        "CurrentValue": "137.50",
    }
    resp = await client.post(TRIGGER_PATH, data=params, headers=_sign(SUB_TOKEN, params))

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["matched"] is True
    assert body["suspended"] is True, "signed monthly breach did not trip the kill switch"

    await db.refresh(acct)
    assert acct.status == "suspended"
    assert "137.50" in (acct.suspended_reason or "")

    rows = await _audit_rows(db, "telephony_suspended")
    assert any(r.resource_id == str(acct.id) for r in rows), "no security-audit row written"
    mine = next(r for r in rows if r.resource_id == str(acct.id))
    assert mine.actor_email == "system:usage-trigger"
    assert mine.tenant_id == acct.tenant_key


@pytest.mark.critical
async def test_spoofed_invalid_signature_is_rejected_and_does_not_suspend(client, db, admin_user):
    """A bogus signature on a KNOWN subaccount is a spoof — 403, no suspend."""
    acct = await _account(db, admin_user)
    params = {
        "AccountSid": acct.subaccount_sid,
        "FriendlyName": "obrain-monthly-spend",
        "CurrentValue": "999",
    }
    resp = await client.post(
        TRIGGER_PATH, data=params, headers={"X-Twilio-Signature": "not-a-real-signature"}
    )
    assert resp.status_code == 403, resp.text
    await db.refresh(acct)
    assert acct.status == "active", "a spoofed callback suspended a tenant"
    assert await _audit_rows(db, "telephony_suspended") == []


@pytest.mark.critical
async def test_missing_signature_is_rejected(client, db, admin_user):
    """No signature at all is also rejected — the endpoint is not open."""
    acct = await _account(db, admin_user)
    params = {"AccountSid": acct.subaccount_sid, "FriendlyName": "obrain-monthly-spend", "CurrentValue": "999"}
    resp = await client.post(TRIGGER_PATH, data=params)
    assert resp.status_code == 403
    await db.refresh(acct)
    assert acct.status == "active"


@pytest.mark.critical
async def test_signature_from_wrong_token_is_rejected(client, db, admin_user):
    """Signed, but with a token that is NOT the subaccount's — still rejected.
    This is the realistic spoof: an attacker signs with their own token."""
    acct = await _account(db, admin_user, token="the-real-subaccount-token")
    params = {"AccountSid": acct.subaccount_sid, "FriendlyName": "obrain-monthly-spend", "CurrentValue": "999"}
    resp = await client.post(
        TRIGGER_PATH, data=params, headers=_sign("an-attacker-controlled-token", params)
    )
    assert resp.status_code == 403
    await db.refresh(acct)
    assert acct.status == "active"


@pytest.mark.critical
async def test_signed_daily_trigger_alerts_but_does_not_suspend(client, db, admin_user):
    """Daily threshold is a soft warning; only monthly is terminal."""
    acct = await _account(db, admin_user)
    params = {"AccountSid": acct.subaccount_sid, "FriendlyName": "obrain-daily-spend", "CurrentValue": "8.00"}
    resp = await client.post(TRIGGER_PATH, data=params, headers=_sign(SUB_TOKEN, params))
    assert resp.status_code == 200
    assert resp.json()["data"]["suspended"] is False
    await db.refresh(acct)
    assert acct.status == "active"


@pytest.mark.critical
async def test_unknown_subaccount_is_ignored(client, db):
    """A callback for a subaccount we don't own is acknowledged, never acted on
    (nothing to suspend, no token to verify against)."""
    params = {"AccountSid": "ACnot-one-of-ours", "FriendlyName": "obrain-monthly-spend", "CurrentValue": "999"}
    resp = await client.post(TRIGGER_PATH, data=params)
    assert resp.status_code == 200
    assert resp.json()["data"]["matched"] is False


def test_provisioning_arms_daily_and_monthly_triggers_at_the_live_route(monkeypatch):
    """create_usage_triggers registers BOTH triggers, pointing POST at the exact
    route the webhook serves. If the callback URL drifts, the kill switch is
    silently disarmed — so pin it."""
    created: list[dict] = []

    class _Triggers:
        def create(self, **kw):
            created.append(kw)
            return type("T", (), {"sid": f"UT{len(created)}"})()

    class _Usage:
        triggers = _Triggers()

    class _Client:
        usage = _Usage()

    monkeypatch.setattr(telephony, "subaccount_client", lambda a: _Client())

    acct = TelephonyAccount(
        tenant_key="t", owner_user_id=uuid.uuid4(), subaccount_sid="ACx",
        encrypted_auth_token="x", status="active",
    )
    sids = telephony.create_usage_triggers(acct, object(), "https://accountant.ocidm.io")

    assert len(sids) == 2
    by_recurring = {c["recurring"]: c for c in created}
    assert "daily" in by_recurring and "monthly" in by_recurring
    for c in created:
        assert c["callback_url"] == "https://accountant.ocidm.io/api/integrations/sms/usage-trigger"
        assert c["callback_method"] == "POST"


# ===========================================================================
# GAP 2 — platform circuit breaker on outbound send + number purchase
# ===========================================================================

@pytest.mark.critical
async def test_circuit_open_blocks_outbound_sms(db, app, admin_user, monkeypatch):
    """Over the platform ceiling, an outbound SMS is refused BEFORE it is billed
    or sent — through the real send_sms path, not just the guard in isolation."""
    await _account(db, admin_user, allow_sms=True)
    await _contact(db, admin_user, "+14155551234")  # recipient must be a contact
    await _circuit_open(monkeypatch)

    with pytest.raises(PlatformCircuitOpen):
        await service.send_sms(db, admin_user, "+14155551234", "hello", app.state.settings)


@pytest.mark.critical
async def test_circuit_open_blocks_number_purchase(client, db, app, admin_user, monkeypatch):
    """Over the ceiling, buying a number is refused with a CLEAR 503, not a
    silent failure — via the real purchase endpoint (router.py:1222 untouched;
    the check is inside enforce_billable_action, a separate guard)."""
    await _account(db, admin_user)
    monkeypatch.setattr(app.state.settings, "twilio_account_sid", "ACtest")
    monkeypatch.setattr(app.state.settings, "twilio_auth_token", "tok")
    await _circuit_open(monkeypatch)

    resp = await client.post(
        "/api/communication/twilio/purchase",
        headers=auth_header(admin_user),
        json={"phone_number": "+14155550000"},
    )
    assert resp.status_code == 503, resp.text
    assert resp.json()["error"]["code"] == "TELEPHONY_CIRCUIT_OPEN"


# ===========================================================================
# Suspended blocks outbound / inbound stays up / reactivate restores
# ===========================================================================

@pytest.mark.critical
async def test_suspended_blocks_outbound_inbound_ok_reactivate_restores(db, app, admin_user, monkeypatch):
    acct = await _account(db, admin_user, allow_sms=True, status="suspended")
    acct.suspended_reason = "monthly cap breached"
    await db.commit()
    await _contact(db, admin_user, "+14155551234")

    # 1) Outbound is refused — the suspension is inherited via ensure_account.
    with pytest.raises(TelephonySuspended):
        await service.send_sms(db, admin_user, "+14155551234", "hi", app.state.settings)

    # 2) Inbound still works — receiving does not touch the suspension gate.
    num = TwilioPhoneNumber(
        id=uuid.uuid4(), phone_number="+13655550000",
        assigned_user_id=admin_user.id, tenant_key=acct.tenant_key,
    )
    db.add(num)
    await db.commit()
    sms = await service.receive_sms(db, "+15551112222", "+13655550000", "inbound hello")
    assert sms.direction == "inbound"
    assert sms.user_id == admin_user.id

    # 3) reactivate() restores outbound, and is audited.
    monkeypatch.setattr(telephony, "_parent_client", _stub_parent_ok)
    await telephony.reactivate(db, acct, app.state.settings, actor_email="operator@ocidm.io")
    await db.refresh(acct)
    assert acct.status == "active"

    async def _ok(_db, _s):
        return True

    monkeypatch.setattr(telephony, "platform_circuit_ok", _ok)
    resolved = await telephony.enforce_billable_action(db, admin_user, app.state.settings, "sms")
    assert resolved.status == "active"

    assert any(r.resource_id == str(acct.id) for r in await _audit_rows(db, "telephony_reactivated"))


# ===========================================================================
# Regression — per-tenant caps still bind (independent of the platform ceiling)
# ===========================================================================

@pytest.mark.critical
async def test_per_tenant_daily_cap_still_blocks(db, admin_user):
    """The existing per-tenant daily cap must keep blocking. Ledger spend over
    the cap -> TelephonyCapReached, regardless of the platform breaker."""
    from app.billing import telephony_credits

    acct = await _account(db, admin_user, allow_sms=True)
    acct.daily_spend_cap_usd = 5.0
    await db.commit()

    db.add(TelephonyLedgerEntry(
        tenant_key=acct.tenant_key,
        period=telephony_credits.current_period(),
        entry_type="usage",
        unit="sms_outbound",
        quantity=1000,
        our_cost_micros=6 * MICROS_PER_USD,
        billed_micros=6 * MICROS_PER_USD,  # $6 billed today > $5 cap
        balance_after_micros=0,
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    with pytest.raises(TelephonyCapReached):
        await telephony_credits.enforce_spend_caps(db, admin_user)
