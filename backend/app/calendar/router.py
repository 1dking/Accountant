
import uuid
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.calendar.schemas import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarEventUpdate,
)
from app.calendar.service import (
    create_event,
    delete_event,
    get_upcoming,
    list_events,
    update_event,
)
from app.core.pagination import PaginationParams, build_pagination_meta, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


@router.get("/events")
async def get_calendar_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> dict:
    events, total_count = await list_events(db, date_from, date_to, pagination)
    return {
        "data": [CalendarEventResponse.model_validate(e) for e in events],
        "meta": build_pagination_meta(total_count, pagination),
    }


@router.post("/events", status_code=201)
async def add_calendar_event(
    body: CalendarEventCreate,
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    event = await create_event(db, current_user.id, body)
    return {"data": CalendarEventResponse.model_validate(event)}


@router.put("/events/{event_id}")
async def edit_calendar_event(
    event_id: uuid.UUID,
    body: CalendarEventUpdate,
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    event = await update_event(db, event_id, current_user.id, body)
    return {"data": CalendarEventResponse.model_validate(event)}


@router.delete("/events/{event_id}")
async def remove_calendar_event(
    event_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await delete_event(db, event_id, current_user.id)
    return {"data": {"message": "Calendar event deleted"}}


@router.get("/upcoming")
async def get_upcoming_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90, description="Number of days to look ahead"),
) -> dict:
    events = await get_upcoming(db, days)
    return {"data": [CalendarEventResponse.model_validate(e) for e in events]}
