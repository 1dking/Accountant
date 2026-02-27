
import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    CreatePaymentLinkRequest,
    CreateSubscriptionRequest,
    PaymentLinkResponse,
    StripeConfigResponse,
    SubscriptionResponse,
)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@router.get("/config", response_model=dict)
async def get_stripe_config(
    request: Request,
    user: User = Depends(get_current_user),
):
    settings = _get_settings(request)
    is_configured = bool(settings.stripe_secret_key and settings.stripe_publishable_key)
    return {
        "data": StripeConfigResponse(
            is_configured=is_configured,
            publishable_key=settings.stripe_publishable_key if is_configured else None,
        ),
    }


# ---------------------------------------------------------------------------
# Payment links (one-time)
# ---------------------------------------------------------------------------


@router.post("/payment-links", response_model=dict)
async def create_payment_link(
    data: CreatePaymentLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    link = await service.create_checkout_session(db, data.invoice_id, user, settings)
    return {"data": PaymentLinkResponse.model_validate(link)}


@router.get("/payment-links/{invoice_id}", response_model=dict)
async def get_payment_link(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    link = await service.get_payment_link(db, invoice_id)
    if not link:
        return {"data": None}
    return {"data": PaymentLinkResponse.model_validate(link)}


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.post("/subscriptions", response_model=dict)
async def create_subscription(
    data: CreateSubscriptionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    sub = await service.create_subscription(db, data, user, settings)
    return {"data": SubscriptionResponse.model_validate(sub)}


@router.get("/subscriptions", response_model=dict)
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subs = await service.list_subscriptions(db, user.id)
    return {
        "data": [SubscriptionResponse.model_validate(s) for s in subs],
    }


@router.delete("/subscriptions/{sub_id}", response_model=dict)
async def cancel_subscription(
    sub_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    sub = await service.cancel_subscription(db, sub_id, user, settings)
    return {"data": SubscriptionResponse.model_validate(sub)}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@router.post("/webhook", response_model=dict)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None),
):
    settings = _get_settings(request)
    payload = await request.body()
    result = await service.handle_webhook_event(
        db, payload, stripe_signature or "", settings
    )
    return {"data": result}
