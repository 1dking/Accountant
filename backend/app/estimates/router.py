
import uuid
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query
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
