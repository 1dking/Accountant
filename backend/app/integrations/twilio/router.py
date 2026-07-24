
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
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
