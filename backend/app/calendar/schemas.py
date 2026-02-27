
import datetime as dt
import uuid

from pydantic import BaseModel, Field

from app.calendar.models import EventType, Recurrence


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    event_type: EventType
    date: dt.date
    recurrence: Recurrence = Recurrence.NONE
    document_id: uuid.UUID | None = None
    is_completed: bool = False


class CalendarEventUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    event_type: EventType | None = None
    date: dt.date | None = None
    recurrence: Recurrence | None = None
    document_id: uuid.UUID | None = None
    is_completed: bool | None = None


class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    event_type: EventType
    date: dt.date
    recurrence: Recurrence
    document_id: uuid.UUID | None = None
    created_by: uuid.UUID
    is_completed: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}
