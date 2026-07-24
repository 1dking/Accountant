"""Emergency patch tests: outbound-voice hole, real credit debit, kill switch,
tenant-scoped contact lookup.

Each test names the hole it closes. Enforcement flags default OFF in tests, so
the ones that assert a block flip them on via the `enforce_on` fixture.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.billing import rate_card, telephony_credits
from app.billing.models import MICROS_PER_USD, TelephonyAccount, TelephonyCredit
from app.contacts.models import Contact


@pytest.fixture
def enforce_on(monkeypatch):
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


async def _add_contact(db: AsyncSession, owner: User, phone: str) -> Contact:
    from app.contacts.models import ContactType

    c = Contact(
        id=uuid.uuid4(), type=ContactType.CLIENT, company_name="Acme",
        phone=phone, created_by=owner.id,
    )
    db.add(c)
    await db.commit()
    return c


# ---------------------------------------------------------------------------
# Item 2 — credit is now a real DECREMENT, not a read
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_debit_actually_decrements_balance(db: AsyncSession, admin_user: User, enforce_on):
    """The core fix: sending debits the balance synchronously. Before, only the
    next-day meter reduced it, so a funded account burst at a frozen balance."""
    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 1.00)
    before = row.balance_micros

    charged = await telephony_credits.debit_now(
        db, admin_user, unit="sms_outbound", action="send"
    )
    assert charged > 0
    after = await telephony_credits.get_balance_micros(db, row.tenant_key)
    assert after == before - charged


@pytest.mark.critical
async def test_debit_blocks_at_insufficient_balance(db: AsyncSession, admin_user: User, enforce_on):
    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 0.001)  # less than one SMS
    with pytest.raises(telephony_credits.InsufficientTelephonyCredit) as exc:
        await telephony_credits.debit_now(db, admin_user, unit="sms_outbound", action="send")
    assert exc.value.status_code == 402


@pytest.mark.critical
async def test_repeated_debits_drain_and_then_block(db: AsyncSession, admin_user: User, enforce_on):
    """A burst can no longer overspend a small balance: each send moves it."""
    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 0.05)  # a few SMS worth
    sent = 0
    with pytest.raises(telephony_credits.InsufficientTelephonyCredit):
        for _ in range(1000):
            await telephony_credits.debit_now(db, admin_user, unit="sms_outbound", action="send")
            sent += 1
    assert 1 <= sent <= 5, sent  # drained after a handful, not unbounded


@pytest.mark.normal
async def test_debit_is_noop_when_flag_off(db: AsyncSession, admin_user: User):
    """Staging: with enforcement off, debit does nothing (no block, no charge)."""
    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 0)
    charged = await telephony_credits.debit_now(db, admin_user, unit="sms_outbound", action="send")
    assert charged == 0
    assert await telephony_credits.get_balance_micros(db, row.tenant_key) == 0


@pytest.mark.normal
async def test_debit_is_noop_for_exempt_account(db: AsyncSession, admin_user: User, monkeypatch):
    monkeypatch.setenv("TELEPHONY_ENFORCE_CREDIT", "true")
    monkeypatch.setenv("TELEPHONY_EXEMPT_EMAILS", admin_user.email)
    await _set_plan(db, admin_user, "starter")
    await _fund(db, admin_user, 0)
    assert await telephony_credits.debit_now(db, admin_user, unit="sms_outbound", action="send") == 0


@pytest.mark.normal
async def test_meter_skips_live_debited_categories():
    """The daily meter must not re-bill outbound SMS/voice — they're debited
    live now, so metering them again would double-charge."""
    from app.billing.telephony_metering import LIVE_DEBITED_CATEGORIES

    assert "sms-outbound" in LIVE_DEBITED_CATEGORIES
    assert "calls-outbound" in LIVE_DEBITED_CATEGORIES


@pytest.mark.normal
async def test_automated_sender_skips_without_credit(db: AsyncSession, admin_user: User, enforce_on):
    """safe_debit_by_user_id returns False (don't send) at zero balance."""
    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 0)
    ok = await telephony_credits.safe_debit_by_user_id(db, admin_user.id, unit="sms_outbound")
    assert ok is False

    await _fund(db, admin_user, 5)
    ok = await telephony_credits.safe_debit_by_user_id(db, admin_user.id, unit="sms_outbound")
    assert ok is True


# ---------------------------------------------------------------------------
# Item 3 — spend caps + kill switch
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_daily_spend_cap_blocks(db: AsyncSession, admin_user: User, enforce_on):
    """The per-tenant spend-cap columns are now enforced, not just displayed."""
    from app.communication.telephony import TelephonyCapReached

    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 100)
    # Provision an account with a tiny daily cap.
    db.add(TelephonyAccount(
        tenant_key=row.tenant_key, owner_user_id=admin_user.id,
        subaccount_sid="ACcap", encrypted_auth_token="x",
        daily_spend_cap_usd=0.02,
    ))
    await db.commit()

    # First debit is under the cap; keep going until the cap trips.
    with pytest.raises(TelephonyCapReached) as exc:
        for _ in range(50):
            await telephony_credits.debit_now(db, admin_user, unit="sms_outbound", action="send")
    assert exc.value.status_code == 402


@pytest.mark.normal
async def test_usage_trigger_creation_is_wired():
    """create_usage_triggers previously had zero callers; ensure_account now
    invokes it. Assert the call is present in the provisioning path."""
    import inspect

    from app.communication import telephony

    src = inspect.getsource(telephony.ensure_account)
    assert "create_usage_triggers" in src


# ---------------------------------------------------------------------------
# Item 4 — tenant-scoped contact lookup
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_contact_lookup_is_tenant_scoped(
    db: AsyncSession, admin_user: User, team_member_user: User
):
    """A number saved by ANOTHER tenant must not resolve for this one."""
    from app.communication.service import _find_contact_by_phone, _tenant_user_ids

    # team_member owns the contact; admin does not.
    await _add_contact(db, team_member_user, "+14155559999")

    # Unscoped (inbound attribution) still finds it — behaviour preserved.
    assert await _find_contact_by_phone(db, "+14155559999") is not None

    # Scoped to admin's tenant — must NOT find another tenant's contact.
    admin_ids = await _tenant_user_ids(db, admin_user)
    assert await _find_contact_by_phone(db, "+14155559999", owner_user_ids=admin_ids) is None

    # Scoped to the owner's tenant — found.
    tm_ids = await _tenant_user_ids(db, team_member_user)
    assert await _find_contact_by_phone(db, "+14155559999", owner_user_ids=tm_ids) is not None


@pytest.mark.critical
async def test_outbound_recipient_rejects_cross_tenant_contact(
    db: AsyncSession, admin_user: User, team_member_user: User
):
    """The outbound SMS recipient gate is now tenant-scoped."""
    from app.communication.guards import RecipientNotAllowed, enforce_recipient_allowed

    await _add_contact(db, team_member_user, "+14155558888")

    # admin has NOT saved this number → rejected even though another tenant has.
    with pytest.raises(RecipientNotAllowed):
        await enforce_recipient_allowed(db, admin_user, "+14155558888")

    # admin saves it → allowed.
    await _add_contact(db, admin_user, "+14155558888")
    await enforce_recipient_allowed(db, admin_user, "+14155558888")


# ---------------------------------------------------------------------------
# Item 1 — voice gate
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_voice_gate_rejects_unattributable_call(db: AsyncSession):
    """No client identity → cannot gate → reject (no dial)."""
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = True

    vr = await _voice_gate(db, None, "+14155551234", _S())
    assert vr is not None
    assert "Hangup" in str(vr)


@pytest.mark.critical
async def test_voice_gate_blocks_non_north_american(db: AsyncSession, admin_user: User):
    """Geo enforced in-app for voice, not just Twilio Console."""
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = True

    vr = await _voice_gate(db, admin_user.id, "+447700900000", _S())  # UK
    assert vr is not None and "not permitted" in str(vr)


@pytest.mark.critical
async def test_voice_gate_blocks_non_contact_and_uncredited(
    db: AsyncSession, admin_user: User, enforce_on
):
    """A US destination that is not a saved contact is rejected before dial."""
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = True

    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 10)
    # Not a contact → blocked.
    vr = await _voice_gate(db, admin_user.id, "+14155551234", _S())
    assert vr is not None and "saved contacts" in str(vr)


@pytest.mark.critical
async def test_voice_gate_allows_funded_call_to_own_contact(
    db: AsyncSession, admin_user: User, enforce_on
):
    """The happy path still works: own contact + credit → allowed, and the
    1-minute hold is debited."""
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = True

    await _set_plan(db, admin_user, "business")
    row = await _fund(db, admin_user, 10)
    await _add_contact(db, admin_user, "+14155551234")
    before = await telephony_credits.get_balance_micros(db, row.tenant_key)

    vr = await _voice_gate(db, admin_user.id, "+14155551234", _S())
    assert vr is None  # allowed
    after = await telephony_credits.get_balance_micros(db, row.tenant_key)
    assert after < before  # 1-minute hold debited


@pytest.mark.normal
async def test_voice_gate_uncredited_blocks(db: AsyncSession, admin_user: User, enforce_on):
    """Own contact but zero balance → blocked on credit."""
    from app.communication.router import _voice_gate

    class _S:
        telephony_exempt_emails = ""
        telephony_enforce_credit = True

    await _set_plan(db, admin_user, "business")
    await _fund(db, admin_user, 0)
    await _add_contact(db, admin_user, "+14155551234")

    vr = await _voice_gate(db, admin_user.id, "+14155551234", _S())
    assert vr is not None and "credit" in str(vr).lower()
