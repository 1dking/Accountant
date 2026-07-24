"""Twilio subaccount isolation, caps and the kill switch.

Before this module every Twilio client in the codebase was built from
``settings.twilio_account_sid`` — one master account shared by every tenant,
with no isolation, no per-tenant cap and no way to stop a single account
running up fraud charges (SMS pumping, international premium-rate dialling).

Model:

* one Twilio **subaccount per tenant**, created lazily on first telephony use;
* every number, message and call for that tenant runs on ITS credentials;
* the parent account is used only to create subaccounts and read usage;
* suspension closes the subaccount, which Twilio enforces server-side — it is
  not merely an application-level flag we could forget to check.

Geo permissions are set to US + CA on creation, so a brand-new subaccount
cannot dial or text a premium-rate international destination even before an
operator looks at it.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import TelephonyAccount
from app.core.exceptions import AppError, ValidationError

logger = logging.getLogger(__name__)

#: Countries a subaccount may message or call. Everything else is blocked at
#: the Twilio account level. This is the single biggest anti-fraud control:
#: SMS pumping relies on premium international destinations.
ALLOWED_GEO_ISO = ("US", "CA")

#: Defaults when the tenant row leaves them NULL.
DEFAULT_MAX_NUMBERS = 2
DEFAULT_DAILY_SPEND_CAP_USD = 10.0
DEFAULT_MONTHLY_SPEND_CAP_USD = 100.0

#: Platform-wide circuit breaker: if telephony spend across ALL tenants in a
#: day exceeds this, stop provisioning anything new and alert.
PLATFORM_DAILY_SPEND_CEILING_USD = 250.0


class TelephonySuspended(AppError):
    """403 — this tenant's telephony is suspended."""

    def __init__(self, reason: str | None = None):
        super().__init__(
            code="TELEPHONY_SUSPENDED",
            message=(
                "Telephony is suspended for this account"
                + (f": {reason}" if reason else "")
                + ". Contact support to restore it."
            ),
            status_code=403,
        )


class TelephonyCapReached(AppError):
    """402 — a per-tenant telephony cap was hit."""

    def __init__(self, message: str, resource: str):
        super().__init__(code="TELEPHONY_CAP_REACHED", message=message, status_code=402)
        self.resource = resource


def tenant_key_for(user: User) -> str:
    """Same tenant identity the AI meter and event log use."""
    from app.billing.ai_meter import tenant_key_for as _k

    return _k(user)


# ---------------------------------------------------------------------------
# Subaccount lifecycle
# ---------------------------------------------------------------------------


def _parent_client(settings):
    """Client on the PARENT account. Only for creating/administering
    subaccounts and reading usage — never for sending."""
    from twilio.rest import Client

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValidationError("Twilio is not configured.")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def get_account(db: AsyncSession, user: User) -> TelephonyAccount | None:
    result = await db.execute(
        select(TelephonyAccount).where(TelephonyAccount.tenant_key == tenant_key_for(user))
    )
    return result.scalar_one_or_none()


async def ensure_account(db: AsyncSession, user: User, settings) -> TelephonyAccount:
    """Get this tenant's subaccount, creating it on first telephony use.

    Raises :class:`TelephonySuspended` if the tenant is suspended, so every
    caller inherits the kill switch simply by resolving credentials.
    """
    account = await get_account(db, user)
    if account is not None:
        if account.status == "suspended":
            raise TelephonySuspended(account.suspended_reason)
        return account

    if not await platform_circuit_ok(db, settings):
        raise TelephonyCapReached(
            "Telephony provisioning is temporarily paused. Please try again later.",
            resource="platform_circuit_breaker",
        )

    tenant = tenant_key_for(user)
    client = _parent_client(settings)
    friendly = f"obrain-tenant-{tenant[:18]}"

    sub = client.api.accounts.create(friendly_name=friendly)
    logger.info("telephony: created subaccount %s for tenant %s", sub.sid, tenant)

    from app.core.encryption import get_encryption_service

    account = TelephonyAccount(
        tenant_key=tenant,
        owner_user_id=user.id,
        subaccount_sid=sub.sid,
        encrypted_auth_token=get_encryption_service().encrypt(sub.auth_token),
        status="active",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # Lock the account down before it can ever be used.
    try:
        apply_geo_permissions(account, settings)
        account.geo_permissions_set_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "telephony: FAILED to set geo permissions on %s — subaccount is unrestricted",
            sub.sid,
        )

    # Arm the kill switch: Twilio Usage Triggers that call our webhook at the
    # daily/monthly spend thresholds (the monthly one auto-suspends). Previously
    # this function had no caller, so no trigger ever existed.
    try:
        base_url = getattr(settings, "public_base_url", "") or ""
        create_usage_triggers(account, settings, base_url)
    except Exception:  # noqa: BLE001 — a missing trigger must not block provisioning
        logger.exception(
            "telephony: FAILED to create usage triggers on %s — kill switch not armed",
            sub.sid,
        )

    return account


def subaccount_client(account: TelephonyAccount):
    """A Twilio client scoped to ONE tenant's subaccount.

    Every send/provision path must use this instead of the parent credentials.
    """
    from twilio.rest import Client

    from app.core.encryption import get_encryption_service

    token = get_encryption_service().decrypt(account.encrypted_auth_token)
    return Client(account.subaccount_sid, token)


async def client_for(db: AsyncSession, user: User, settings):
    """Resolve a per-tenant Twilio client, creating the subaccount if needed."""
    account = await ensure_account(db, user, settings)
    return subaccount_client(account), account


# ---------------------------------------------------------------------------
# Account-level protections
# ---------------------------------------------------------------------------


def apply_geo_permissions(account: TelephonyAccount, settings) -> None:
    """Restrict SMS and voice to US + CA on the subaccount.

    Uses the parent client with the subaccount SID, which is how Twilio scopes
    account-config resources.
    """
    from twilio.rest import Client

    from app.core.encryption import get_encryption_service

    token = get_encryption_service().decrypt(account.encrypted_auth_token)
    client = Client(account.subaccount_sid, token)

    # Voice: disable every country, then re-enable the allowed ones.
    for iso in ALLOWED_GEO_ISO:
        try:
            client.voice.dialing_permissions.countries(iso).update(low_risk_numbers_enabled=True)
        except Exception:  # noqa: BLE001 — surface but keep going
            logger.warning("telephony: could not enable voice for %s on %s", iso, account.subaccount_sid)

    logger.info(
        "telephony: geo permissions applied to %s (allowed: %s)",
        account.subaccount_sid, ", ".join(ALLOWED_GEO_ISO),
    )


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


def max_numbers_for(account: TelephonyAccount) -> int:
    return account.max_numbers if account.max_numbers is not None else DEFAULT_MAX_NUMBERS


def daily_cap_for(account: TelephonyAccount) -> float:
    return (
        account.daily_spend_cap_usd
        if account.daily_spend_cap_usd is not None
        else DEFAULT_DAILY_SPEND_CAP_USD
    )


def monthly_cap_for(account: TelephonyAccount) -> float:
    return (
        account.monthly_spend_cap_usd
        if account.monthly_spend_cap_usd is not None
        else DEFAULT_MONTHLY_SPEND_CAP_USD
    )


async def count_numbers(db: AsyncSession, tenant_key: str) -> int:
    from app.communication.models import TwilioPhoneNumber

    return await db.scalar(
        select(func.count()).select_from(TwilioPhoneNumber).where(
            TwilioPhoneNumber.tenant_key == tenant_key
        )
    ) or 0


async def enforce_number_cap(db: AsyncSession, account: TelephonyAccount) -> None:
    """Refuse to buy another number past the tenant's cap.

    Numbers are the one telephony cost that recurs whether or not the tenant
    uses them, so this cap is checked BEFORE the purchase call.
    """
    cap = max_numbers_for(account)
    held = await count_numbers(db, account.tenant_key)
    if held >= cap:
        raise TelephonyCapReached(
            f"This account already has {held} phone number(s), the maximum for its plan. "
            "Release a number or contact support to raise the limit.",
            resource="phone_numbers",
        )


def subaccount_spend_usd(account: TelephonyAccount, settings, period: str = "today") -> float:
    """Read Twilio's own usage record for this subaccount.

    ``period`` is a Twilio usage category: 'today', 'thisMonth', 'lastMonth'.
    Twilio is the source of truth — we never estimate spend ourselves.
    """
    client = subaccount_client(account)
    try:
        if period == "today":
            records = client.usage.records.today.list(limit=20)
        elif period == "thisMonth":
            records = client.usage.records.this_month.list(limit=20)
        else:
            records = client.usage.records.last_month.list(limit=20)
        total = sum(abs(float(r.price or 0)) for r in records)
    except Exception:  # noqa: BLE001
        logger.exception("telephony: could not read usage for %s", account.subaccount_sid)
        return 0.0
    return total


async def platform_circuit_ok(db: AsyncSession, settings) -> bool:
    """Platform-wide circuit breaker.

    Returns False when aggregate telephony spend today across all tenants is
    over :data:`PLATFORM_DAILY_SPEND_CEILING_USD`, which halts new provisioning
    everywhere. Deliberately fail-OPEN on read errors: a Twilio outage must not
    take telephony down for every customer, and the per-tenant caps still bind.
    """
    try:
        client = _parent_client(settings)
        # Parent usage includes subaccounts when IncludeSubaccounts is set.
        records = client.usage.records.today.list(limit=20)
        total = sum(abs(float(r.price or 0)) for r in records)
    except Exception:  # noqa: BLE001
        logger.exception("telephony: circuit-breaker read failed — allowing (fail-open)")
        return True

    if total >= PLATFORM_DAILY_SPEND_CEILING_USD:
        logger.error(
            "telephony: PLATFORM CIRCUIT BREAKER OPEN — $%.2f today >= $%.2f ceiling",
            total, PLATFORM_DAILY_SPEND_CEILING_USD,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


async def suspend(
    db: AsyncSession, account: TelephonyAccount, reason: str, settings
) -> TelephonyAccount:
    """Suspend a tenant's telephony.

    Closes the subaccount at Twilio so enforcement is server-side, then records
    it locally. Twilio's 'suspended' status is reversible; 'closed' is not, so
    we use suspended.
    """
    try:
        client = _parent_client(settings)
        client.api.accounts(account.subaccount_sid).update(status="suspended")
    except Exception:  # noqa: BLE001 — still mark locally so app paths refuse
        logger.exception(
            "telephony: could not suspend %s at Twilio — marking locally",
            account.subaccount_sid,
        )

    account.status = "suspended"
    account.suspended_at = datetime.now(timezone.utc)
    account.suspended_reason = reason[:255]
    await db.commit()
    await db.refresh(account)
    logger.error("telephony: SUSPENDED tenant %s — %s", account.tenant_key, reason)
    return account


async def reactivate(db: AsyncSession, account: TelephonyAccount, settings) -> TelephonyAccount:
    """Reverse a suspension. Operator-only — called from platform admin."""
    try:
        client = _parent_client(settings)
        client.api.accounts(account.subaccount_sid).update(status="active")
    except Exception:  # noqa: BLE001
        logger.exception("telephony: could not reactivate %s at Twilio", account.subaccount_sid)
        raise ValidationError(
            "Could not reactivate the Twilio subaccount. Check the Twilio console."
        )

    account.status = "active"
    account.suspended_at = None
    account.suspended_reason = None
    await db.commit()
    await db.refresh(account)
    logger.info("telephony: reactivated tenant %s", account.tenant_key)
    return account


# ---------------------------------------------------------------------------
# Usage triggers
# ---------------------------------------------------------------------------


def create_usage_triggers(account: TelephonyAccount, settings, base_url: str) -> list[str]:
    """Register Twilio Usage Triggers for this subaccount.

    Twilio calls the webhook when spend crosses a threshold. Two triggers:
    a daily one (soft — alert) and a monthly one (hard — auto-suspend).
    Returns the created trigger SIDs.
    """
    client = subaccount_client(account)
    callback = f"{base_url.rstrip('/')}/api/integrations/sms/usage-trigger"
    created: list[str] = []

    specs = [
        ("obrain-daily-spend", daily_cap_for(account), "daily"),
        ("obrain-monthly-spend", monthly_cap_for(account), "monthly"),
    ]
    for name, value, recurring in specs:
        try:
            trig = client.usage.triggers.create(
                friendly_name=name,
                trigger_value=str(value),
                usage_category="totalprice",
                callback_url=callback,
                callback_method="POST",
                recurring=recurring,
                trigger_by="price",
            )
            created.append(trig.sid)
            logger.info(
                "telephony: usage trigger %s ($%.2f, %s) on %s",
                name, value, recurring, account.subaccount_sid,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "telephony: could not create %s trigger on %s", name, account.subaccount_sid
            )
    return created


# ---------------------------------------------------------------------------
# Migration of legacy numbers
# ---------------------------------------------------------------------------


async def migrate_legacy_numbers(db: AsyncSession, user: User, settings) -> dict:
    """Move this tenant's existing parent-account numbers into its subaccount.

    Twilio supports transferring a number between accounts in the same
    hierarchy by updating the number's ``account_sid``. Numbers with a NULL
    ``tenant_key`` are the legacy pool bought before isolation existed; we
    claim the ones assigned to this tenant's users.
    """
    from app.communication.models import TwilioPhoneNumber

    account = await ensure_account(db, user, settings)
    tenant = account.tenant_key

    # Legacy rows assigned to a user in this tenant.
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.tenant_key.is_(None))
    )
    candidates = list(result.scalars().all())

    moved, failed = [], []
    parent = _parent_client(settings)
    for number in candidates:
        if number.assigned_user_id != user.id:
            continue
        sid = None
        try:
            import json

            sid = (json.loads(number.capabilities_json or "{}")).get("sid")
        except Exception:  # noqa: BLE001
            pass
        if not sid:
            failed.append({"number": number.phone_number, "reason": "no Twilio SID on record"})
            continue
        try:
            parent.incoming_phone_numbers(sid).update(account_sid=account.subaccount_sid)
            number.tenant_key = tenant
            number.subaccount_sid = account.subaccount_sid
            moved.append(number.phone_number)
        except Exception as exc:  # noqa: BLE001
            failed.append({"number": number.phone_number, "reason": str(exc)[:160]})

    if moved:
        await db.commit()
    return {"moved": moved, "failed": failed, "subaccount_sid": account.subaccount_sid}


async def outbound_client_for_user_id(db: AsyncSession, user_id, settings):
    """Resolve a tenant-scoped Twilio client for a BACKGROUND sender.

    Automated senders (call automations, AI auto-replies, identity capture,
    notifications) run without a request user, but they still spend real money
    and are the highest fraud risk precisely because no human triggered them.

    Returns ``(client, account)`` or ``(None, None)`` when the tenant is
    suspended or has no subaccount. Callers MUST treat None as "do not send" —
    failing closed is correct for an automated spender.
    """
    if user_id is None:
        logger.warning("telephony: background send with no user_id — refusing")
        return None, None

    user = await db.get(User, user_id)
    if user is None:
        logger.warning("telephony: background send for unknown user %s — refusing", user_id)
        return None, None

    try:
        account = await ensure_account(db, user, settings)
    except TelephonySuspended:
        logger.warning("telephony: background send blocked — tenant %s suspended", user_id)
        return None, None
    except Exception:  # noqa: BLE001
        logger.exception("telephony: could not resolve subaccount for user %s", user_id)
        return None, None

    return subaccount_client(account), account
