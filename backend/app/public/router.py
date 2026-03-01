"""FastAPI router for public access (no authentication required)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

from .models import ResourceType
from .schemas import AcceptEstimateRequest, PublicDocumentResponse
from .service import (
    accept_estimate,
    create_public_payment_intent,
    get_company_branding,
    get_resource_data,
    get_token_by_value,
    increment_view_count,
)

router = APIRouter()


def _determine_actions(resource_type: str, status: str) -> list[str]:
    """Determine available actions based on resource type and status."""
    if resource_type == ResourceType.ESTIMATE:
        if status in ("draft", "sent"):
            return ["accept", "decline"]
        return []
    elif resource_type == ResourceType.INVOICE:
        if status in ("sent", "viewed", "overdue", "partially_paid"):
            return ["pay"]
        return []
    return []


@router.get("/view/{token}")
async def view_public_document(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """View a shared document (estimate or invoice) via public token."""
    settings = request.app.state.settings
    pat = await get_token_by_value(db, token)
    await increment_view_count(db, pat)

    document = await get_resource_data(db, pat)
    company = await get_company_branding(db)
    actions = _determine_actions(pat.resource_type, document.get("status", ""))
    is_signed = bool(document.get("signed_by_name"))
    stripe_configured = bool(settings.stripe_secret_key)

    stripe_publishable_key = settings.stripe_publishable_key if stripe_configured else None

    return {
        "data": PublicDocumentResponse(
            resource_type=pat.resource_type.value,
            document=document,
            company=company,
            actions=actions,
            is_signed=is_signed,
            stripe_configured=stripe_configured,
            stripe_publishable_key=stripe_publishable_key,
        ).model_dump()
    }


@router.post("/view/{token}/accept")
async def accept_public_estimate(
    token: str,
    data: AcceptEstimateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Accept an estimate with a digital signature via a public link."""
    pat = await get_token_by_value(db, token)
    signer_ip = request.client.host if request.client else "unknown"
    result = await accept_estimate(db, pat, data.signature_data, data.signer_name, signer_ip)
    return {"data": result}


@router.post("/view/{token}/pay")
async def pay_public_invoice(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create a Stripe PaymentIntent for an invoice accessed via public token."""
    settings = request.app.state.settings
    pat = await get_token_by_value(db, token)
    result = await create_public_payment_intent(db, pat, settings)
    return {"data": result}
