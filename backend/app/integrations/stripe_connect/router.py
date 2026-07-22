
import logging
import urllib.parse

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .models import StripeConnectAccount
from .schemas import StripeConnectStatusResponse

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


@router.get("/connect", response_model=dict)
async def connect_stripe_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    settings = _get_settings(request)
    base_url = str(request.base_url).rstrip("/")
    url = await service.start_onboarding(db, user, settings, base_url=base_url)
    return {"data": {"url": url}}


@router.get("/return/{stripe_account_id}")
async def stripe_connect_return(
    stripe_account_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    settings = _get_settings(request)
    base_url = settings.public_base_url.rstrip("/")
    try:
        account_row = await service.refresh_account_status(db, stripe_account_id, settings)
        if account_row is None:
            return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&error=account_not_found")
        if account_row.details_submitted:
            return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&connected=true")
        return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&pending=true")
    except Exception as exc:
        logging.getLogger(__name__).error("Stripe Connect return failed: %s", exc, exc_info=True)
        error_msg = urllib.parse.quote(str(exc)[:200])
        return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&error={error_msg}")


@router.get("/refresh/{stripe_account_id}")
async def stripe_connect_refresh(
    stripe_account_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    settings = _get_settings(request)
    base_url = settings.public_base_url.rstrip("/")
    result = await db.execute(
        select(StripeConnectAccount).where(StripeConnectAccount.stripe_account_id == stripe_account_id)
    )
    account_row = result.scalar_one_or_none()
    if account_row is None:
        return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&error=account_not_found")

    try:
        owner = await db.get(User, account_row.user_id)
        req_base_url = str(request.base_url).rstrip("/")
        url = await service.start_onboarding(db, owner, settings, base_url=req_base_url)
        return RedirectResponse(url=url)
    except Exception as exc:
        logging.getLogger(__name__).error("Stripe Connect refresh failed: %s", exc, exc_info=True)
        error_msg = urllib.parse.quote(str(exc)[:200])
        return RedirectResponse(url=f"{base_url}/settings?tab=stripe_connect&error={error_msg}")


# ---------------------------------------------------------------------------
# Status / disconnect
# ---------------------------------------------------------------------------


@router.get("/status", response_model=dict)
async def get_connect_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account_row = await service.get_connect_account_for_user(db, user.id)
    if account_row is None:
        return {"data": None}
    return {"data": StripeConnectStatusResponse.model_validate(account_row)}


@router.delete("/disconnect", response_model=dict)
async def disconnect_stripe_account(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    await service.disconnect(db, user.id)
    return {"data": {"detail": "Stripe account disconnected"}}


# ---------------------------------------------------------------------------
# Webhook (Connect-scoped — separate endpoint/secret from app.integrations.stripe)
# ---------------------------------------------------------------------------


@router.post("/webhook", response_model=dict)
async def stripe_connect_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(...),
):
    settings = _get_settings(request)
    payload = await request.body()
    result = await service.handle_connect_webhook_event(db, payload, stripe_signature, settings)
    return {"data": result}
