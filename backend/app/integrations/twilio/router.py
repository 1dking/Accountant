
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import SendInvoiceSmsRequest, SendSmsRequest, SmsLogResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/send", response_model=dict)
async def send_sms(
    data: SendSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_sms(db, data.to, data.message, user, settings)
    return {"data": SmsLogResponse.model_validate(log)}


@router.post("/send-invoice-sms", response_model=dict)
async def send_invoice_sms(
    data: SendInvoiceSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_invoice_sms(db, data.invoice_id, data.to, user, settings)
    return {"data": SmsLogResponse.model_validate(log)}


@router.post("/send-reminder-sms", response_model=dict)
async def send_reminder_sms(
    data: SendInvoiceSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_payment_reminder_sms(
        db, data.invoice_id, data.to, user, settings
    )
    return {"data": SmsLogResponse.model_validate(log)}


@router.get("/logs", response_model=dict)
async def list_sms_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    logs, meta = await service.list_sms_logs(db, user.id, pagination)
    return {"data": [SmsLogResponse.model_validate(log) for log in logs], "meta": meta}


# ---------------------------------------------------------------------------
# Usage triggers + kill switch
# ---------------------------------------------------------------------------


@router.post("/usage-trigger")
async def usage_trigger_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Twilio Usage Trigger callback — the kill switch.

    Twilio POSTs here when a subaccount crosses a spend threshold. No auth:
    the payload is validated by matching AccountSid to a subaccount we own,
    and the only side effect is suspension (fail-safe, never fail-open).

    Daily threshold  -> alert the operator.
    Monthly threshold -> alert AND suspend, because a monthly breach means the
    daily alerts were already ignored.
    """
    settings = request.app.state.settings
    form = await request.form()
    account_sid = str(form.get("AccountSid", ""))
    trigger_name = str(form.get("FriendlyName", ""))
    current_value = str(form.get("CurrentValue", "0"))

    from sqlalchemy import select as _select

    from app.billing.models import TelephonyAccount
    from app.communication import telephony

    result = await db.execute(
        _select(TelephonyAccount).where(TelephonyAccount.subaccount_sid == account_sid)
    )
    account = result.scalar_one_or_none()
    if account is None:
        # Not one of ours — acknowledge without acting.
        logger.warning("usage-trigger: unknown subaccount %s", account_sid)
        return {"data": {"received": True, "matched": False}}

    hard = "monthly" in trigger_name.lower()
    reason = f"{trigger_name} threshold breached at ${current_value}"

    logger.error(
        "TELEPHONY USAGE TRIGGER: tenant=%s subaccount=%s trigger=%s value=$%s hard=%s",
        account.tenant_key, account_sid, trigger_name, current_value, hard,
    )

    try:
        from app.notifications.service import create_notification

        await create_notification(
            db,
            user_id=account.owner_user_id,
            type="telephony_spend_alert",
            title="Telephony spend alert",
            message=(
                f"Phone/SMS spend reached ${current_value}. "
                + ("Telephony has been suspended." if hard else "Approaching the limit.")
            ),
            resource_type="telephony",
            resource_id=str(account.id),
        )
    except Exception:  # noqa: BLE001 — alerting must not block suspension
        logger.exception("usage-trigger: could not notify owner")

    suspended = False
    if hard and account.status != "suspended":
        await telephony.suspend(db, account, reason, settings)
        suspended = True

    return {"data": {"received": True, "matched": True, "suspended": suspended}}


@router.get("/telephony/status")
async def telephony_status(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """This tenant's telephony posture: caps, numbers held, suspension state."""
    from app.communication import telephony

    account = await telephony.get_account(db, current_user)
    if account is None:
        return {"data": {"provisioned": False}}

    return {
        "data": {
            "provisioned": True,
            "subaccount_sid": account.subaccount_sid,
            "status": account.status,
            "suspended_at": account.suspended_at,
            "suspended_reason": account.suspended_reason,
            "numbers_held": await telephony.count_numbers(db, account.tenant_key),
            "max_numbers": telephony.max_numbers_for(account),
            "daily_spend_cap_usd": telephony.daily_cap_for(account),
            "monthly_spend_cap_usd": telephony.monthly_cap_for(account),
            "geo_restricted_to": list(telephony.ALLOWED_GEO_ISO),
        }
    }


@router.post("/telephony/migrate-numbers")
async def migrate_numbers(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Move this tenant's legacy parent-account numbers into its subaccount."""
    from app.communication import telephony

    settings = request.app.state.settings
    return {"data": await telephony.migrate_legacy_numbers(db, current_user, settings)}


# ---------------------------------------------------------------------------
# Operator-only capability grants (Step 2 — least privilege)
# ---------------------------------------------------------------------------


class CapabilityGrantRequest(BaseModel):
    """Explicit per-capability grants. Omitted fields are left unchanged.

    There is deliberately no tenant-facing equivalent of this endpoint: the only
    writer of these columns is an operator, so a tenant cannot self-escalate.
    """

    allow_voice_outbound: bool | None = None
    allow_voice_inbound: bool | None = None
    allow_sms: bool | None = None
    allow_mms: bool | None = None
    allow_number_purchase: bool | None = None
    allow_markup: bool | None = None


@router.get("/telephony/capabilities/{tenant_key}")
async def get_capabilities(
    tenant_key: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Operator view of one tenant's granted capabilities."""
    from app.platform_admin.router import require_platform_admin

    await require_platform_admin(request, current_user)

    account = await _load_account(db, tenant_key)
    return {"data": _capability_dto(account)}


@router.put("/telephony/capabilities/{tenant_key}")
async def set_capabilities(
    tenant_key: str,
    body: CapabilityGrantRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Operator grants/revokes capabilities for one tenant. Audited."""
    from datetime import datetime, timezone

    from app.audit.service import AuditAction, AuditResult, safe_record_audit
    from app.platform_admin.router import require_platform_admin

    await require_platform_admin(request, current_user)
    account = await _load_account(db, tenant_key)

    changes: dict[str, bool] = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if getattr(account, field) != value:
            changes[field] = value
            setattr(account, field, value)

    if changes:
        account.capabilities_updated_by = current_user.id
        account.capabilities_updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)
        await safe_record_audit(
            db,
            action=AuditAction.FEATURE_FLAG_CHANGED,
            result=AuditResult.SUCCESS,
            actor_id=current_user.id,
            actor_email=current_user.email,
            tenant_id=tenant_key,
            resource_type="telephony_account",
            resource_id=str(account.id),
            metadata={"telephony_capabilities": changes},
        )

    return {"data": _capability_dto(account), "meta": {"changed": changes}}


async def _load_account(db: AsyncSession, tenant_key: str):
    from sqlalchemy import select as _select

    from app.billing.models import TelephonyAccount
    from app.core.exceptions import NotFoundError

    row = await db.execute(
        _select(TelephonyAccount).where(TelephonyAccount.tenant_key == tenant_key)
    )
    account = row.scalar_one_or_none()
    if account is None:
        raise NotFoundError("Telephony account", tenant_key)
    return account


def _capability_dto(account) -> dict:
    from app.communication.telephony import CAPABILITIES

    return {
        "tenant_key": account.tenant_key,
        "subaccount_sid": account.subaccount_sid,
        "status": account.status,
        "suspended_reason": account.suspended_reason,
        "capabilities": {name: bool(getattr(account, field)) for name, field in CAPABILITIES.items()},
        "allow_markup": bool(account.allow_markup),
        "updated_at": account.capabilities_updated_at,
    }
