from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar.models import CalendarEvent
from app.calendar.schemas import CalendarEventCreate, CalendarEventUpdate
from app.collaboration.service import log_activity
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams


async def create_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: CalendarEventCreate,
) -> CalendarEvent:
    """Create a new calendar event."""
    event = CalendarEvent(
        title=data.title,
        description=data.description,
        event_type=data.event_type,
        date=data.date,
        recurrence=data.recurrence,
        document_id=data.document_id,
        created_by=user_id,
        is_completed=data.is_completed,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await log_activity(
        db,
        user_id=user_id,
        action="event_created",
        resource_type="calendar_event",
        resource_id=str(event.id),
        details={"title": event.title, "date": str(event.date)},
    )

    return event


async def list_events(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    pagination: PaginationParams | None = None,
) -> tuple[list[CalendarEvent], int]:
    """List calendar events with optional date range filter, paginated."""
    query = select(CalendarEvent)
    count_query = select(func.count()).select_from(CalendarEvent)

    if date_from is not None:
        query = query.where(CalendarEvent.date >= date_from)
        count_query = count_query.where(CalendarEvent.date >= date_from)
    if date_to is not None:
        query = query.where(CalendarEvent.date <= date_to)
        count_query = count_query.where(CalendarEvent.date <= date_to)

    total_count = await db.scalar(count_query) or 0

    query = query.order_by(CalendarEvent.date.asc())
    if pagination is not None:
        query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await db.execute(query)
    events = list(result.scalars().all())
    return events, total_count


async def update_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CalendarEventUpdate,
) -> CalendarEvent:
    """Update a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError("CalendarEvent", str(event_id))

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    await log_activity(
        db,
        user_id=user_id,
        action="event_updated",
        resource_type="calendar_event",
        resource_id=str(event.id),
        details={"title": event.title, "fields_updated": list(update_data.keys())},
    )

    return event


async def delete_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError("CalendarEvent", str(event_id))

    event_title = event.title
    await db.delete(event)
    await db.commit()

    await log_activity(
        db,
        user_id=user_id,
        action="event_deleted",
        resource_type="calendar_event",
        resource_id=str(event_id),
        details={"title": event_title},
    )


async def get_upcoming(
    db: AsyncSession,
    days: int = 7,
) -> list[CalendarEvent]:
    """Return events within the next N days (not completed)."""
    today = date.today()
    end_date = today + timedelta(days=days)

    result = await db.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.date >= today,
            CalendarEvent.date <= end_date,
            CalendarEvent.is_completed == False,  # noqa: E712
        )
        .order_by(CalendarEvent.date.asc())
    )
    return list(result.scalars().all())
