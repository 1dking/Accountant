"""Pydantic schemas for the meetings module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.meetings.models import MeetingStatus, ParticipantRole, RecordingStatus


# ---------------------------------------------------------------------------
# Meeting schemas
# ---------------------------------------------------------------------------


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scheduled_start: datetime
    scheduled_end: datetime | None = None
    contact_id: uuid.UUID | None = None
    record_meeting: bool = False
    room_type: str = "group-small"
    participant_emails: list[str] = Field(default_factory=list)
    create_calendar_event: bool = True


class MeetingUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    contact_id: uuid.UUID | None = None
    record_meeting: bool | None = None
    status: MeetingStatus | None = None


# ---------------------------------------------------------------------------
# Participant schemas
# ---------------------------------------------------------------------------


class MeetingParticipantAdd(BaseModel):
    user_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    guest_name: str | None = None
    guest_email: str | None = None
    role: str = "participant"


class MeetingParticipantResponse(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    user_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    guest_name: str | None
    guest_email: str | None
    role: ParticipantRole
    join_token: str | None
    joined_at: datetime | None
    left_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Recording schemas
# ---------------------------------------------------------------------------


class MeetingRecordingResponse(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    status: RecordingStatus
    duration_seconds: int | None
    file_size: int | None
    storage_path: str | None
    mime_type: str
    egress_id: str | None
    started_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Meeting response schemas
# ---------------------------------------------------------------------------


class MeetingResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: MeetingStatus
    scheduled_start: datetime
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    livekit_room_name: str
    record_meeting: bool
    created_by: uuid.UUID
    contact_id: uuid.UUID | None
    calendar_event_id: uuid.UUID | None
    participants: list[MeetingParticipantResponse] = []
    recordings: list[MeetingRecordingResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeetingListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: MeetingStatus
    scheduled_start: datetime
    scheduled_end: datetime | None
    record_meeting: bool
    contact_id: uuid.UUID | None
    participant_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Join token schema
# ---------------------------------------------------------------------------


class GuestJoinRequest(BaseModel):
    guest_name: str = Field(min_length=1, max_length=255)


class JoinTokenResponse(BaseModel):
    token: str
    room_name: str
    identity: str
