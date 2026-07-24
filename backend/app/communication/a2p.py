"""A2P 10DLC registration, per tenant, under the tenant's own subaccount.

US carriers require brand + campaign registration before a 10-digit long code
may send application-to-person SMS. Unregistered traffic is filtered or blocked
outright, so this is not optional for a US SMS product.

Shape of the flow (all under the tenant's subaccount, so trust lives with the
tenant, not with us):

    Secondary Customer Profile  ->  Brand  ->  Campaign  ->  approved

Carrier review of a campaign takes **10-15 days**, so ``status`` is surfaced to
the tenant as an explicit waiting state and :func:`require_sms_registered`
keeps SMS locked until it reaches ``approved``.

Registration fees (brand, campaign, monthly campaign renewal) are billed
through the rate card like any other unit.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import A2PRegistration
from app.core.exceptions import AppError, ValidationError

logger = logging.getLogger(__name__)

#: Ordered pipeline. Index is used to decide what the next step is.
STATUSES = (
    "not_started",
    "profile_pending",
    "brand_pending",
    "campaign_pending",
    "approved",
    "rejected",
)

#: Roughly how long carriers take, shown to the tenant so the wait is expected
#: rather than alarming.
TYPICAL_REVIEW_DAYS = "10-15 days"


class SmsNotRegistered(AppError):
    """403 — SMS is locked until A2P registration is approved."""

    def __init__(self, status: str):
        friendly = {
            "not_started": "Register your business for A2P 10DLC to enable SMS.",
            "profile_pending": "Your business profile is under review.",
            "brand_pending": "Your brand registration is under review.",
            "campaign_pending": (
                f"Your messaging campaign is under carrier review (typically {TYPICAL_REVIEW_DAYS})."
            ),
            "rejected": "Your A2P registration was rejected — review the details and resubmit.",
        }.get(status, "A2P 10DLC registration is not complete.")
        super().__init__(
            code="SMS_NOT_REGISTERED",
            message=f"{friendly} US carriers require this before SMS can be sent.",
            status_code=403,
        )
        self.status = status


async def get_registration(db: AsyncSession, user: User) -> A2PRegistration | None:
    from app.billing.ai_meter import tenant_key_for

    result = await db.execute(
        select(A2PRegistration).where(A2PRegistration.tenant_key == tenant_key_for(user))
    )
    return result.scalar_one_or_none()


async def get_or_create(db: AsyncSession, user: User) -> A2PRegistration:
    from app.billing.ai_meter import tenant_key_for

    reg = await get_registration(db, user)
    if reg is not None:
        return reg
    reg = A2PRegistration(
        tenant_key=tenant_key_for(user), owner_user_id=user.id, status="not_started"
    )
    db.add(reg)
    await db.commit()
    await db.refresh(reg)
    return reg


async def status_for(db: AsyncSession, user: User) -> dict:
    """What the tenant sees on the SMS settings screen."""
    reg = await get_or_create(db, user)
    sms_enabled = reg.status == "approved"
    return {
        "status": reg.status,
        "sms_enabled": sms_enabled,
        "is_pending": reg.status in ("profile_pending", "brand_pending", "campaign_pending"),
        "typical_review_time": TYPICAL_REVIEW_DAYS,
        "business_name": reg.business_name,
        "submitted_at": reg.submitted_at,
        "approved_at": reg.approved_at,
        "failure_reason": reg.failure_reason,
        "profile_sid": reg.profile_sid,
        "brand_sid": reg.brand_sid,
        "campaign_sid": reg.campaign_sid,
        "next_step": _next_step(reg.status),
    }


def _next_step(status: str) -> str:
    return {
        "not_started": "Submit your business details to begin registration.",
        "profile_pending": "Waiting on business profile approval.",
        "brand_pending": "Waiting on brand approval.",
        "campaign_pending": f"Waiting on carrier campaign review ({TYPICAL_REVIEW_DAYS}).",
        "approved": "Registered — SMS is enabled.",
        "rejected": "Fix the reported issue and resubmit.",
    }.get(status, "")


# ---------------------------------------------------------------------------
# Who actually needs 10DLC
# ---------------------------------------------------------------------------

#: North American toll-free area codes. Toll-free numbers are NOT part of
#: 10DLC — they use Twilio's separate Toll-Free Verification programme.
TOLLFREE_NPAS = frozenset({"800", "833", "844", "855", "866", "877", "888"})

#: A2P 10DLC is a US carrier programme. Canadian long codes are exempt.
A2P_REQUIRED_COUNTRIES = frozenset({"US"})

#: Canadian area codes (NANP). Needed because Twilio's IncomingPhoneNumber
#: resource does not expose iso_country in the SDK version we run, and US/CA
#: share the +1 country code — so origin is inferred from the NPA instead.
#: Deterministic and free; the alternative (Lookup API) is billable per call.
CANADA_NPAS = frozenset({
    "204", "226", "236", "249", "250", "263", "289",
    "306", "343", "354", "365", "367", "368", "382", "387",
    "403", "416", "418", "428", "431", "437", "438", "450", "468", "474",
    "506", "514", "519", "548", "579", "581", "584", "587",
    "604", "613", "639", "647", "672", "683",
    "705", "709", "742", "753", "778", "780", "782",
    "807", "819", "825", "867", "873", "879",
    "902", "905",
})


def classify_number(phone_number: str | None, iso_country: str | None = None) -> str:
    """Classify a sending number: "us_longcode" | "ca_longcode" | "tollfree"
    | "unknown".

    US and Canadian numbers share the +1 country code, so origin CANNOT be
    derived from the number string — ``iso_country`` comes from Twilio at
    purchase time. Toll-free IS derivable, from the NPA.
    """
    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        npa = digits[1:4]
    elif len(digits) == 10:
        npa = digits[:3]
    else:
        npa = ""

    if npa in TOLLFREE_NPAS:
        return "tollfree"

    # Explicit country wins when we have it.
    country = (iso_country or "").upper()
    if country == "US":
        return "us_longcode"
    if country == "CA":
        return "ca_longcode"

    # Otherwise infer from the area code. Canada's NPAs are a fixed set, so a
    # match is definitive; any other NANP code is US.
    if npa:
        return "ca_longcode" if npa in CANADA_NPAS else "us_longcode"
    return "unknown"


def number_requires_a2p(phone_number: str | None, iso_country: str | None = None) -> bool:
    """Does this sending number need an approved 10DLC campaign?

    Only US long codes do. Canadian long codes are outside the programme, and
    toll-free uses Toll-Free Verification instead — blocking either on 10DLC
    would be wrong.

    ``unknown`` (origin not yet recorded) returns False deliberately: refusing
    to send because WE never stored the country is our bug, not the tenant's.
    The backfill fills these in; until then the other gates still apply.
    """
    return classify_number(phone_number, iso_country) in (
        c.lower() + "_longcode" for c in A2P_REQUIRED_COUNTRIES
    )


def is_exempt_account(user: User, settings=None) -> bool:
    """Operator-owned accounts bypass telephony enforcement entirely.

    Same comma-separated-email shape as ``super_admin_emails``.
    """
    if settings is None:
        from app.config import Settings

        settings = Settings()
    raw = getattr(settings, "telephony_exempt_emails", "") or ""
    exempt = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return bool(exempt) and (user.email or "").lower() in exempt


async def require_sms_registered(
    db: AsyncSession,
    user: User,
    *,
    from_number: str | None = None,
    iso_country: str | None = None,
    settings=None,
) -> None:
    """Gate outbound SMS on an approved 10DLC campaign — where it applies.

    A2P 10DLC is a **US carrier programme**, so the requirement attaches to the
    SENDING number, not to the account:

      * US long code  -> approved campaign required (fail-closed; unregistered
                         US traffic gets filtered and burns the number)
      * CA long code  -> exempt, outside the programme
      * toll-free     -> exempt from 10DLC; Toll-Free Verification is the
                         separate path and is not enforced here
      * unknown origin-> allowed (see number_requires_a2p)

    Operator-owned accounts in ``telephony_exempt_emails`` bypass entirely.

    Staged behind ``telephony_enforce_a2p``. Checked inside the guard rather
    than at call sites so every sender inherits the rollout state.
    """
    if settings is None:
        from app.config import Settings

        settings = Settings()

    if not settings.telephony_enforce_a2p:
        return
    if is_exempt_account(user, settings):
        return
    if not number_requires_a2p(from_number, iso_country):
        logger.debug(
            "a2p: skipping 10DLC gate for %s (%s)",
            from_number, classify_number(from_number, iso_country),
        )
        return

    reg = await get_registration(db, user)
    if reg is None or reg.status != "approved":
        raise SmsNotRegistered(reg.status if reg else "not_started")


async def submit_registration(
    db: AsyncSession, user: User, payload: dict, settings
) -> A2PRegistration:
    """Collect brand details and start the pipeline under the tenant subaccount.

    Fees are charged to the tenant's prepaid credit BEFORE submitting, because
    Twilio bills us for brand and campaign registration the moment they are
    created — this is real money leaving on the tenant's behalf.
    """
    from app.billing import telephony_credits
    from app.billing.rate_card import require_enabled
    from app.communication import telephony

    reg = await get_or_create(db, user)
    if reg.status in ("profile_pending", "brand_pending", "campaign_pending", "approved"):
        raise ValidationError(
            f"Registration is already in progress (status: {reg.status})."
        )

    required = ("business_name", "ein", "contact_email", "use_case")
    missing = [f for f in required if not payload.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    # Charge brand + campaign registration up front.
    for unit, label in (("a2p_brand", "brand registration"), ("a2p_campaign", "campaign registration")):
        rate = await require_enabled(db, user, unit)
        await telephony_credits.require_credit(db, user, unit=unit, action=f"submit {label}")

    reg.business_name = payload.get("business_name")
    reg.business_type = payload.get("business_type")
    reg.ein = payload.get("ein")
    reg.website = payload.get("website")
    reg.contact_email = payload.get("contact_email")
    reg.contact_phone = payload.get("contact_phone")
    reg.address_json = json.dumps(payload.get("address") or {})
    reg.use_case = payload.get("use_case")
    reg.sample_messages_json = json.dumps(payload.get("sample_messages") or [])
    reg.failure_reason = None
    reg.submitted_at = datetime.now(timezone.utc)

    account = await telephony.ensure_account(db, user, settings)

    try:
        _submit_to_twilio(reg, account, settings)
        reg.status = "campaign_pending"
    except Exception as exc:  # noqa: BLE001
        logger.exception("a2p: submission failed for tenant %s", reg.tenant_key)
        reg.status = "rejected"
        reg.failure_reason = str(exc)[:500]
        await db.commit()
        raise ValidationError(
            f"Could not submit A2P registration: {str(exc)[:200]}"
        )

    await db.commit()
    await db.refresh(reg)

    # Fees are only debited once submission succeeded.
    from app.billing.ai_meter import tenant_key_for

    tenant = tenant_key_for(user)
    for unit, label in (("a2p_brand", "A2P brand registration"), ("a2p_campaign", "A2P campaign registration")):
        rate = await require_enabled(db, user, unit)
        await telephony_credits.charge(
            db, tenant, unit=unit, quantity=1.0, rate=rate,
            external_ref=f"a2p:{tenant}:{unit}:{reg.id}",
            description=label,
        )

    logger.info("a2p: submitted registration for tenant %s", reg.tenant_key)
    return reg


def _submit_to_twilio(reg: A2PRegistration, account, settings) -> None:
    """Create the Secondary Customer Profile, Brand and Campaign.

    Kept in one place and deliberately thin: the Trust Hub API surface is large
    and version-sensitive, and none of it can be exercised without real
    credentials and a real EIN. Failures propagate to the caller, which records
    them on the registration row so the tenant sees a reason rather than a
    silent stall.
    """
    from app.communication.telephony import subaccount_client

    client = subaccount_client(account)

    profile = client.trusthub.v1.customer_profiles.create(
        friendly_name=f"{reg.business_name} (O-Brain)",
        email=reg.contact_email,
        policy_sid="RNdfbf3fae0e1107f8aded0e7cead80bf5",  # Twilio's secondary-profile policy
    )
    reg.profile_sid = profile.sid

    brand = client.messaging.v1.brand_registrations.create(
        customer_profile_bundle_sid=profile.sid,
        a2p_profile_bundle_sid=profile.sid,
    )
    reg.brand_sid = brand.sid

    service = client.messaging.v1.services.create(
        friendly_name=f"{reg.business_name} messaging"
    )
    campaign = client.messaging.v1.services(service.sid).us_app_to_person.create(
        brand_registration_sid=brand.sid,
        description=(reg.use_case or "Customer notifications")[:1024],
        message_flow="Customers opt in via our web form or by texting us first.",
        message_samples=json.loads(reg.sample_messages_json or "[]") or [
            "Your appointment is confirmed for tomorrow at 2pm.",
            "Your invoice #1234 is ready: https://example.com/pay",
        ],
        us_app_to_person_usecase=(reg.use_case or "MIXED"),
        has_embedded_links=True,
        has_embedded_phone=False,
    )
    reg.campaign_sid = campaign.sid


async def refresh_status(db: AsyncSession, reg: A2PRegistration, settings) -> A2PRegistration:
    """Poll Twilio for campaign approval. Called from the scheduler."""
    from app.billing.models import TelephonyAccount
    from app.communication.telephony import subaccount_client

    if reg.status not in ("brand_pending", "campaign_pending"):
        return reg

    result = await db.execute(
        select(TelephonyAccount).where(TelephonyAccount.tenant_key == reg.tenant_key)
    )
    account = result.scalar_one_or_none()
    if account is None or not reg.campaign_sid:
        return reg

    try:
        client = subaccount_client(account)
        brand = client.messaging.v1.brand_registrations(reg.brand_sid).fetch()
        state = (getattr(brand, "status", "") or "").upper()
    except Exception:  # noqa: BLE001
        logger.exception("a2p: status refresh failed for %s", reg.tenant_key)
        return reg

    reg.last_checked_at = datetime.now(timezone.utc)
    if state in ("APPROVED", "VERIFIED", "REGISTERED"):
        reg.status = "approved"
        reg.approved_at = datetime.now(timezone.utc)
        logger.info("a2p: APPROVED for tenant %s", reg.tenant_key)
        try:
            from app.notifications.service import create_notification

            await create_notification(
                db,
                user_id=reg.owner_user_id,
                type="a2p_approved",
                title="SMS is now enabled",
                message="Your A2P 10DLC registration was approved. You can now send text messages.",
                resource_type="a2p_registration",
                resource_id=str(reg.id),
            )
        except Exception:  # noqa: BLE001
            logger.exception("a2p: approval notification failed")
    elif state in ("FAILED", "REJECTED"):
        reg.status = "rejected"
        reg.failure_reason = getattr(brand, "failure_reason", None) or "Carrier rejected the registration."

    await db.commit()
    await db.refresh(reg)
    return reg


async def refresh_all_pending(db: AsyncSession, settings) -> int:
    """Scheduler entry point: poll every pending registration."""
    rows = (
        await db.execute(
            select(A2PRegistration).where(
                A2PRegistration.status.in_(("brand_pending", "campaign_pending"))
            )
        )
    ).scalars().all()

    updated = 0
    for reg in rows:
        before = reg.status
        await refresh_status(db, reg, settings)
        if reg.status != before:
            updated += 1
    return updated
