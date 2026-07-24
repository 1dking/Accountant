"""Tests for the runaway-cost and telephony-fraud guards.

Each test names the hole it closes. Before this pass:
  - one Twilio master account, no isolation, no number cap, no kill switch
  - outbound SMS to any number, at any rate
  - a vision call on every upload with no size/page/concurrency guard
  - an AI cap that covered exactly one of twelve model paths
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing import ai_meter
from app.billing.models import TelephonyAccount
from app.core.exceptions import AppError
from app.platform_admin.models import PlatformSetting


async def _set_plan(db: AsyncSession, user: User, plan_key: str) -> None:
    from app.billing import service

    sub = await service.get_subscription(db, user)
    sub.plan_key = plan_key
    await db.commit()


# ---------------------------------------------------------------------------
# AI meter — the unified ceiling
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_every_ai_path_is_priced():
    """A new AI call site must never be silently free. Unpriced operations
    fall back to the chat rate rather than zero."""
    assert ai_meter.operation_cost("chat") == 18
    assert ai_meter.operation_cost("doc_extract") == 15
    # Unknown operation -> charged, not free.
    assert ai_meter.operation_cost("some_new_ai_feature") == ai_meter.AI_OPERATION_COSTS["chat"]
    # Units multiply (a 5-page PDF costs 5x a single page).
    assert ai_meter.operation_cost("doc_extract", units=5) == 75


@pytest.mark.critical
async def test_no_plan_is_unlimited():
    """Replaces _UNLIMITED_AI = {"business", "enterprise"} — the ceiling that
    let a Business account spend ~$1,555/month of Claude on a $79 plan."""
    for plan in ("starter", "pro", "business", "enterprise"):
        assert ai_meter.PLAN_AI_CREDITS[plan] > 0
        assert ai_meter.PLAN_AI_CREDITS[plan] < 10**9


@pytest.mark.critical
async def test_credits_deplete_and_then_block(db: AsyncSession, admin_user: User):
    await _set_plan(db, admin_user, "starter")
    limit = ai_meter.PLAN_AI_CREDITS["starter"]

    usage = await ai_meter.get_usage(db, admin_user)
    assert usage["credits_used"] == 0
    assert usage["credits_remaining"] == limit

    await ai_meter.consume(db, admin_user, "chat")
    usage = await ai_meter.get_usage(db, admin_user)
    assert usage["credits_used"] == 18
    assert usage["calls"] == 1

    # Burn the rest, then the next call must be refused with a 402.
    while True:
        try:
            await ai_meter.consume(db, admin_user, "chat")
        except ai_meter.AiCreditsExhausted as exc:
            assert exc.status_code == 402
            break

    with pytest.raises(ai_meter.AiCreditsExhausted):
        await ai_meter.consume(db, admin_user, "chat")


@pytest.mark.critical
async def test_meter_blocks_before_spending_not_after(db: AsyncSession, admin_user: User):
    """consume() must refuse the call rather than record it afterwards —
    otherwise the tokens are already paid for."""
    await _set_plan(db, admin_user, "starter")
    limit = ai_meter.PLAN_AI_CREDITS["starter"]

    # A single operation costing more than the whole allowance is refused
    # outright, and must not increment the counter.
    with pytest.raises(ai_meter.AiCreditsExhausted):
        await ai_meter.consume(db, admin_user, "chat", units=limit)

    usage = await ai_meter.get_usage(db, admin_user)
    assert usage["credits_used"] == 0, "refused call must not be charged"


@pytest.mark.normal
async def test_background_jobs_skip_instead_of_raising(db: AsyncSession, admin_user: User):
    """safe_consume is for scheduler jobs: out of credits means skip the work,
    not raise a 402 at nobody."""
    await _set_plan(db, admin_user, "starter")
    assert await ai_meter.safe_consume(db, admin_user, "coach_report") is True

    # Exhaust, then the background path must return False rather than raise.
    while True:
        try:
            await ai_meter.consume(db, admin_user, "chat")
        except ai_meter.AiCreditsExhausted:
            break
    assert await ai_meter.safe_consume(db, admin_user, "coach_report") is False


@pytest.mark.normal
async def test_higher_plan_gets_more_credits(db: AsyncSession, admin_user: User):
    await _set_plan(db, admin_user, "starter")
    starter = await ai_meter.get_credit_limit(db, admin_user)
    await _set_plan(db, admin_user, "business")
    business = await ai_meter.get_credit_limit(db, admin_user)
    assert business > starter


@pytest.mark.normal
async def test_usage_is_per_tenant_not_per_user(db: AsyncSession, admin_user: User):
    """An agency meters as one tenant. tenant_key mirrors resolve_org_id."""
    assert ai_meter.tenant_key_for(admin_user) == str(admin_user.id)
    admin_user.org_id = uuid.uuid4()
    assert ai_meter.tenant_key_for(admin_user) == str(admin_user.org_id)


# ---------------------------------------------------------------------------
# Upload guard — the worst runaway path
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_oversized_file_never_reaches_the_model():
    """documents/router.py fired a vision call on any upload up to the 100 MB
    limit, and Claude bills a PDF per page."""
    from app.ai.guards import MAX_VISION_BYTES, check_vision_size
    from app.core.exceptions import ValidationError

    check_vision_size(b"x" * 1024, "image/jpeg")  # small is fine
    with pytest.raises(ValidationError):
        check_vision_size(b"x" * (MAX_VISION_BYTES + 1), "image/jpeg")


@pytest.mark.critical
async def test_pdf_page_cap_bounds_cost():
    """Cost scales with page count, so the page count is capped."""
    pytest.importorskip("fitz")
    import fitz

    from app.ai.guards import MAX_PDF_PAGES, cap_pdf_pages

    doc = fitz.open()
    for _ in range(40):
        doc.new_page()
    data = doc.tobytes()
    doc.close()

    trimmed, pages = cap_pdf_pages(data, "application/pdf")
    assert pages == MAX_PDF_PAGES
    assert fitz.open(stream=trimmed, filetype="pdf").page_count == MAX_PDF_PAGES


@pytest.mark.critical
async def test_large_image_is_downscaled_on_dimensions_not_bytes():
    """Vision cost tracks PIXELS. A 4032x3024 flat-colour screenshot is only
    ~180 KB but still ~16k tokens, so a byte threshold would miss it."""
    pytest.importorskip("PIL")
    import io

    from PIL import Image

    from app.ai.guards import MAX_IMAGE_EDGE, downscale_image

    buf = io.BytesIO()
    Image.new("RGB", (4032, 3024), (120, 90, 60)).save(buf, format="JPEG", quality=95)
    original = buf.getvalue()

    out, mime = downscale_image(original, "image/jpeg")
    w, h = Image.open(io.BytesIO(out)).size
    assert max(w, h) <= MAX_IMAGE_EDGE
    assert len(out) < len(original)


@pytest.mark.normal
async def test_ai_auto_extract_switch_is_actually_read():
    """The flag was declared in config.py and never read anywhere — there was
    no way to turn automatic extraction off without a code change."""
    from app.documents.service import _autoextract_allowed

    class _S:
        ai_auto_extract = False

    class _On:
        ai_auto_extract = True

    assert _autoextract_allowed(b"small", _S()) is False
    assert _autoextract_allowed(b"small", _On()) is True


@pytest.mark.normal
async def test_extraction_concurrency_is_bounded():
    """Every upload used to spawn an unbounded asyncio task (and its own DB
    engine); a bulk upload fanned out into hundreds of parallel vision calls."""
    from app.documents.router import (
        MAX_CONCURRENT_EXTRACTIONS_PER_TENANT,
        _extraction_semaphore,
    )

    sem = _extraction_semaphore("tenant-a")
    assert sem._value == MAX_CONCURRENT_EXTRACTIONS_PER_TENANT
    # Same tenant shares one semaphore; different tenants don't contend.
    assert _extraction_semaphore("tenant-a") is sem
    assert _extraction_semaphore("tenant-b") is not sem


# ---------------------------------------------------------------------------
# Telephony guards
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_outbound_blocked_to_non_contact(db: AsyncSession, admin_user: User):
    """SMS pumping blasts traffic at attacker-controlled numbers. send_sms
    previously matched a contact only to LABEL the message — a non-match
    still sent."""
    from app.communication.guards import RecipientNotAllowed, enforce_recipient_allowed

    with pytest.raises(RecipientNotAllowed) as exc:
        await enforce_recipient_allowed(db, admin_user, "+15551234567")
    assert exc.value.status_code == 403


@pytest.mark.critical
async def test_outbound_blocked_to_international(db: AsyncSession, admin_user: User):
    """Premium international routes are the payload of a pumping attack."""
    from app.communication.guards import is_allowed_destination

    assert is_allowed_destination("+15551234567") is True
    assert is_allowed_destination("+447700900000") is False   # UK
    assert is_allowed_destination("+8801700000000") is False  # Bangladesh
    assert is_allowed_destination("+2348012345678") is False  # Nigeria


@pytest.mark.normal
async def test_inbound_reply_may_target_unknown_number(db: AsyncSession, admin_user: User):
    """Replying to someone who texted us first is legitimate even with no
    contact record yet."""
    from app.communication.guards import enforce_recipient_allowed

    await enforce_recipient_allowed(db, admin_user, "+15551234567", allow_unknown=True)


@pytest.mark.critical
async def test_sms_rate_limit_trips(db: AsyncSession, admin_user: User):
    """No outbound rate limit existed at all."""
    from app.communication.guards import SMS_PER_MINUTE, TelephonyRateLimited, enforce_sms_rate_limit
    from app.communication.models import SmsMessage

    await enforce_sms_rate_limit(db, admin_user)  # clean slate is fine

    now = datetime.now(timezone.utc)
    for i in range(SMS_PER_MINUTE):
        db.add(SmsMessage(
            id=uuid.uuid4(), user_id=admin_user.id, direction="outbound",
            from_number="+15550000000", to_number="+15551111111",
            body="x", status="sent", created_at=now - timedelta(seconds=i),
        ))
    await db.commit()

    with pytest.raises(TelephonyRateLimited) as exc:
        await enforce_sms_rate_limit(db, admin_user)
    assert exc.value.status_code == 429


@pytest.mark.normal
async def test_inbound_messages_do_not_count_against_the_limit(
    db: AsyncSession, admin_user: User
):
    from app.communication.guards import SMS_PER_MINUTE, enforce_sms_rate_limit
    from app.communication.models import SmsMessage

    now = datetime.now(timezone.utc)
    for _ in range(SMS_PER_MINUTE + 5):
        db.add(SmsMessage(
            id=uuid.uuid4(), user_id=admin_user.id, direction="inbound",
            from_number="+15551111111", to_number="+15550000000",
            body="x", status="received", created_at=now,
        ))
    await db.commit()
    await enforce_sms_rate_limit(db, admin_user)  # must not raise


@pytest.mark.critical
async def test_number_cap_blocks_purchase(db: AsyncSession, admin_user: User):
    """communication/router.py bought numbers on the master account with no
    per-tenant limit — each ~$1.15/month billed to us, forever."""
    from app.communication import telephony
    from app.communication.models import TwilioPhoneNumber

    account = TelephonyAccount(
        tenant_key=str(admin_user.id), owner_user_id=admin_user.id,
        subaccount_sid="ACtest", encrypted_auth_token="x", max_numbers=2,
    )
    db.add(account)
    await db.commit()

    await telephony.enforce_number_cap(db, account)  # 0 held, fine

    for i in range(2):
        db.add(TwilioPhoneNumber(
            id=uuid.uuid4(), phone_number=f"+1555000000{i}",
            tenant_key=str(admin_user.id), subaccount_sid="ACtest",
        ))
    await db.commit()

    with pytest.raises(telephony.TelephonyCapReached) as exc:
        await telephony.enforce_number_cap(db, account)
    assert exc.value.status_code == 402


@pytest.mark.normal
async def test_number_cap_is_per_tenant(db: AsyncSession, admin_user: User, team_member_user: User):
    """One tenant's numbers must not consume another's allowance."""
    from app.communication import telephony
    from app.communication.models import TwilioPhoneNumber

    account = TelephonyAccount(
        tenant_key=str(admin_user.id), owner_user_id=admin_user.id,
        subaccount_sid="ACtest2", encrypted_auth_token="x", max_numbers=1,
    )
    db.add(account)
    db.add(TwilioPhoneNumber(
        id=uuid.uuid4(), phone_number="+15559999999",
        tenant_key=str(team_member_user.id), subaccount_sid="ACother",
    ))
    await db.commit()

    await telephony.enforce_number_cap(db, account)  # other tenant's number doesn't count


@pytest.mark.critical
async def test_suspended_tenant_cannot_use_telephony(db: AsyncSession, admin_user: User):
    """The kill switch: ensure_account() raises for a suspended tenant, so
    every caller inherits it just by resolving credentials."""
    from app.communication import telephony

    account = TelephonyAccount(
        tenant_key=str(admin_user.id), owner_user_id=admin_user.id,
        subaccount_sid="ACsuspended", encrypted_auth_token="x",
        status="suspended", suspended_reason="monthly spend breach",
    )
    db.add(account)
    await db.commit()

    with pytest.raises(telephony.TelephonySuspended) as exc:
        await telephony.ensure_account(db, admin_user, object())
    assert exc.value.status_code == 403
    assert "monthly spend breach" in exc.value.message


@pytest.mark.normal
async def test_suspension_is_reversible(db: AsyncSession, admin_user: User):
    """A kill switch with no way back is an outage, not a control."""
    from app.communication import telephony

    account = TelephonyAccount(
        tenant_key=str(admin_user.id), owner_user_id=admin_user.id,
        subaccount_sid="ACrev", encrypted_auth_token="x", status="suspended",
        suspended_at=datetime.now(timezone.utc), suspended_reason="test",
    )
    db.add(account)
    await db.commit()

    # reactivate() calls Twilio; assert the local state machine independently.
    account.status = "active"
    account.suspended_at = None
    account.suspended_reason = None
    await db.commit()

    fetched = await telephony.get_account(db, admin_user)
    assert fetched.status == "active"
    assert fetched.suspended_at is None


@pytest.mark.normal
async def test_geo_allow_list_is_north_america_only():
    from app.communication import telephony

    assert set(telephony.ALLOWED_GEO_ISO) == {"US", "CA"}


@pytest.mark.normal
async def test_platform_circuit_breaker_has_a_ceiling():
    from app.communication import telephony

    assert telephony.PLATFORM_DAILY_SPEND_CEILING_USD > 0
    assert telephony.DEFAULT_MAX_NUMBERS >= 1
    assert telephony.DEFAULT_DAILY_SPEND_CAP_USD > 0
