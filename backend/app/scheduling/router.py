"""FastAPI router for the native calendar & scheduling module."""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.scheduling import service
from app.scheduling.schemas import (
    BookingCreate,
    BookingListItem,
    BookingResponse,
    BookingUpdate,
    CalendarCreate,
    CalendarListItem,
    CalendarResponse,
    CalendarUpdate,
    MemberAdd,
    MemberResponse,
    PublicCalendarInfo,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Static / public paths first
# ---------------------------------------------------------------------------


@router.get("/public/{slug}")
async def get_public_calendar(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    date: str = Query(None),
) -> dict:
    cal = await service.get_calendar_by_slug(db, slug)
    slots = []
    if date:
        slots = await service.get_available_slots(db, cal.id, date)
    return {
        "data": PublicCalendarInfo(
            id=cal.id,
            name=cal.name,
            description=cal.description,
            duration_minutes=cal.duration_minutes,
            timezone=cal.timezone,
            available_slots=slots,
        )
    }


@router.post("/public/{slug}/book", status_code=201)
async def public_book(
    slug: str,
    data: BookingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    cal = await service.get_calendar_by_slug(db, slug)
    booking = await service.create_booking(db, cal.id, data)
    return {"data": BookingResponse.model_validate(booking)}


@router.get("/bookings/all")
async def list_all_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    bookings, total = await service.list_bookings(db, status=status, page=page, page_size=page_size)
    return {
        "data": [BookingListItem.model_validate(b) for b in bookings],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Calendars CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_calendars(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    calendars, total = await service.list_calendars(db, current_user.id, page, page_size)
    return {
        "data": [CalendarListItem.model_validate(c) for c in calendars],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("", status_code=201)
async def create_calendar(
    data: CalendarCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    cal = await service.create_calendar(db, data, current_user)
    return {"data": CalendarResponse.model_validate(cal)}


@router.get("/{calendar_id}")
async def get_calendar(
    calendar_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    cal = await service.get_calendar(db, calendar_id)
    return {"data": CalendarResponse.model_validate(cal)}


@router.put("/{calendar_id}")
async def update_calendar(
    calendar_id: uuid.UUID,
    data: CalendarUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    cal = await service.update_calendar(db, calendar_id, data)
    return {"data": CalendarResponse.model_validate(cal)}


@router.delete("/{calendar_id}")
async def delete_calendar(
    calendar_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_calendar(db, calendar_id)
    return {"data": {"message": "Calendar deleted"}}


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/members")
async def list_members(
    calendar_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    members = await service.list_members(db, calendar_id)
    return {"data": [MemberResponse.model_validate(m) for m in members]}


@router.post("/{calendar_id}/members", status_code=201)
async def add_member(
    calendar_id: uuid.UUID,
    data: MemberAdd,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    member = await service.add_member(db, calendar_id, data.user_id, data.priority or 0)
    return {"data": MemberResponse.model_validate(member)}


@router.delete("/{calendar_id}/members/{member_id}")
async def remove_member(
    calendar_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.remove_member(db, calendar_id, member_id)
    return {"data": {"message": "Member removed"}}


# ---------------------------------------------------------------------------
# Bookings (under /{calendar_id})
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/bookings")
async def list_bookings(
    calendar_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    bookings, total = await service.list_bookings(
        db, calendar_id=calendar_id, status=status, page=page, page_size=page_size
    )
    return {
        "data": [BookingListItem.model_validate(b) for b in bookings],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/{calendar_id}/bookings", status_code=201)
async def create_booking(
    calendar_id: uuid.UUID,
    data: BookingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    booking = await service.create_booking(db, calendar_id, data)
    return {"data": BookingResponse.model_validate(booking)}


@router.get("/{calendar_id}/bookings/{booking_id}")
async def get_booking(
    calendar_id: uuid.UUID,
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    booking = await service.get_booking(db, booking_id)
    return {"data": BookingResponse.model_validate(booking)}


@router.put("/{calendar_id}/bookings/{booking_id}")
async def update_booking(
    calendar_id: uuid.UUID,
    booking_id: uuid.UUID,
    data: BookingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    booking = await service.update_booking(db, booking_id, data)
    return {"data": BookingResponse.model_validate(booking)}


@router.post("/{calendar_id}/bookings/{booking_id}/cancel")
async def cancel_booking(
    calendar_id: uuid.UUID,
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    reason: str | None = Query(None),
) -> dict:
    booking = await service.cancel_booking(db, booking_id, reason)
    return {"data": BookingResponse.model_validate(booking)}


# ---------------------------------------------------------------------------
# Available slots
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/slots")
async def get_available_slots(
    calendar_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    date: str = Query(...),
) -> dict:
    slots = await service.get_available_slots(db, calendar_id, date)
    return {"data": slots}
