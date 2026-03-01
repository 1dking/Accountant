
import uuid
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role
from app.estimates import service
from app.estimates.models import EstimateStatus
from app.estimates.schemas import (
    EstimateCreate,
    EstimateFilter,
    EstimateListItem,
    EstimateResponse,
    EstimateUpdate,
)
from app.invoicing.schemas import InvoiceResponse
from app.public.models import ResourceType
from app.public.service import create_public_token, revoke_token

router = APIRouter()


@router.get("")
async def list_estimates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    status: EstimateStatus | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> dict:
    filters = EstimateFilter(
        search=search, status=status, contact_id=contact_id,
        date_from=date_from, date_to=date_to,
    )
    estimates, meta = await service.list_estimates(db, filters, pagination)
    return {"data": [EstimateListItem.model_validate(est) for est in estimates], "meta": meta}


@router.post("", status_code=201)
async def create_estimate(
    data: EstimateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    estimate = await service.create_estimate(db, data, current_user)
    return {"data": EstimateResponse.model_validate(estimate)}


@router.get("/{estimate_id}")
async def get_estimate(
    estimate_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    estimate = await service.get_estimate(db, estimate_id)
    return {"data": EstimateResponse.model_validate(estimate)}


@router.put("/{estimate_id}")
async def update_estimate(
    estimate_id: uuid.UUID,
    data: EstimateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    estimate = await service.update_estimate(db, estimate_id, data, current_user)
    return {"data": EstimateResponse.model_validate(estimate)}


@router.delete("/{estimate_id}")
async def delete_estimate(
    estimate_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_estimate(db, estimate_id)
    return {"data": {"message": "Estimate deleted"}}


@router.post("/{estimate_id}/convert-to-invoice", status_code=201)
async def convert_to_invoice(
    estimate_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    invoice = await service.convert_to_invoice(db, estimate_id, current_user)
    return {"data": InvoiceResponse.model_validate(invoice)}


@router.post("/{estimate_id}/share", status_code=201)
async def share_estimate(
    estimate_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a shareable public link for an estimate."""
    # Verify estimate exists
    await service.get_estimate(db, estimate_id)
    token = await create_public_token(db, ResourceType.ESTIMATE, estimate_id, current_user)
    base_url = str(request.base_url).rstrip("/")
    shareable_url = f"{base_url}/view/{token.token}"
    return {"data": {"id": str(token.id), "token": token.token, "resource_type": "estimate", "resource_id": str(estimate_id), "shareable_url": shareable_url}}


@router.delete("/{estimate_id}/share/{token_id}")
async def revoke_estimate_share(
    estimate_id: uuid.UUID,
    token_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Revoke a shareable link for an estimate."""
    await revoke_token(db, token_id, current_user)
    return {"data": {"message": "Share link revoked"}}


@router.post("/{estimate_id}/send-email")
async def send_estimate_email_endpoint(
    estimate_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Send an estimate via email to the client."""
    from app.email.service import send_estimate_email

    result = await send_estimate_email(db, estimate_id, None, current_user)
    return {"data": result}
