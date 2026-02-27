"""FastAPI router for accounting period closing/locking."""


import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import period_service
from app.accounting.period_schemas import PeriodClose, PeriodReopen, PeriodResponse
from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


@router.get("/periods")
async def list_periods(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return all accounting periods."""
    periods = await period_service.list_periods(db)
    return {"data": [PeriodResponse.model_validate(p) for p in periods]}


@router.post("/periods/close", status_code=201)
async def close_period(
    data: PeriodClose,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Close (lock) an accounting period."""
    period = await period_service.close_period(
        db,
        year=data.year,
        month=data.month,
        user=current_user,
        notes=data.notes,
    )
    return {"data": PeriodResponse.model_validate(period)}


@router.post("/periods/{period_id}/reopen")
async def reopen_period(
    period_id: uuid.UUID,
    data: PeriodReopen,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Reopen a previously closed accounting period."""
    period = await period_service.reopen_period(
        db, period_id, current_user, notes=data.notes
    )
    return {"data": PeriodResponse.model_validate(period)}
