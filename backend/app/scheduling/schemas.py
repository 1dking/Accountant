"""Pydantic schemas for the native calendar & scheduling module."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Calendars ---

class CalendarCreate(BaseModel):
    name: str = Field(max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    calendar_type: Optional[str] = "personal"
    duration_minutes: Optional[int] = 30
    buffer_minutes: Optional[int] = 0
    max_advance_days: Optional[int] = 60
    min_notice_hours: Optional[int] = 1
    availability_json: Optional[str] = None
    timezone: Optional[str] = "America/New_York"
    confirmation_message: Optional[str] = None
    reminder_enabled: Optional[bool] = True
    google_calendar_id: Optional[str] = None
    google_sync_enabled: Optional[bool] = False


class CalendarUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    calendar_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    buffer_minutes: Optional[int] = None
    max_advance_days: Optional[int] = None
    min_notice_hours: Optional[int] = None
    availability_json: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    confirmation_message: Optional[str] = None
    reminder_enabled: Optional[bool] = None
    google_calendar_id: Optional[str] = None
    google_sync_enabled: Optional[bool] = None


class CalendarResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    calendar_type: str
    duration_minutes: int
    buffer_minutes: int
    max_advance_days: int
    min_notice_hours: int
    availability_json: Optional[str] = None
    timezone: str
    is_active: bool
    confirmation_message: Optional[str] = None
    reminder_enabled: bool
    google_calendar_id: Optional[str] = None
    google_sync_enabled: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    calendar_type: str
    duration_minutes: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Members ---

class MemberAdd(BaseModel):
    user_id: uuid.UUID
    priority: Optional[int] = 0


class MemberResponse(BaseModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Bookings ---

class BookingCreate(BaseModel):
    guest_name: str = Field(max_length=255)
    guest_email: str = Field(max_length=255)
    guest_phone: Optional[str] = None
    guest_notes: Optional[str] = None
    start_time: datetime


class BookingUpdate(BaseModel):
    status: Optional[str] = None
    cancellation_reason: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    assigned_user_id: Optional[uuid.UUID] = None
    guest_name: str
    guest_email: str
    guest_phone: Optional[str] = None
    guest_notes: Optional[str] = None
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: Optional[str] = None
    google_event_id: Optional[str] = None
    confirmation_sent: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingListItem(BaseModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    guest_name: str
    guest_email: str
    start_time: datetime
    end_time: datetime
    status: str
    assigned_user_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Available slots ---

class AvailableSlot(BaseModel):
    start: datetime
    end: datetime


class PublicCalendarInfo(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    duration_minutes: int
    timezone: str
    available_slots: list[AvailableSlot] = []
