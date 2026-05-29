"""Pydantic schemas for the meetings module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.meetings.models import (
    LobbyStatus, MeetingStatus, MeetingTemplate, ParticipantRole, RecordingStatus,
)


# ---------------------------------------------------------------------------
# Meeting schemas
# ---------------------------------------------------------------------------


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    # Commit 8 — optional so the same schema covers instant meetings
    # (omit → use now()) and scheduled meetings.
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    contact_id: uuid.UUID | None = None
    record_meeting: bool = False
    # Commit 16 — template biases AI behavior. When omitted, defaults
    # to GENERIC. The host picks via the dropdown in NewMeetingPage.
    template: MeetingTemplate = MeetingTemplate.GENERIC
    room_type: str = "group-small"
    participant_emails: list[str] = Field(default_factory=list)
    create_calendar_event: bool = True


class InstantMeetingCreate(BaseModel):
    """Commit 8 — Google-Meet "+ New meeting" button. Title is optional;
    backend defaults to 'Instant meeting' if omitted. No participants
    on creation — host shares the slug URL to invite ad-hoc."""
    title: str | None = Field(None, max_length=255)
    record_meeting: bool = False
    # Commit 16 — template available on instant meetings too. The new-
    # meeting dropdown can pre-select Discovery vs Internal Sync.
    template: MeetingTemplate = MeetingTemplate.GENERIC


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
    # Commit 8 — surface lobby state so the host's lobby panel can
    # render Admit/Deny without a separate fetch.
    lobby_status: LobbyStatus | None = None
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
    # Commit 8 — shareable Google-Meet-style slug. Always present for
    # new rows; legacy rows are backfilled by the migration.
    slug: str | None = None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    livekit_room_name: str
    record_meeting: bool
    template: MeetingTemplate = MeetingTemplate.GENERIC
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
    slug: str | None = None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    record_meeting: bool
    template: MeetingTemplate = MeetingTemplate.GENERIC
    contact_id: uuid.UUID | None
    participant_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Commit 8 — lobby flow schemas (Google-Meet-style guest knock + admit)
# ---------------------------------------------------------------------------


class PublicMeetingInfo(BaseModel):
    """Minimal meeting metadata exposed to unauthenticated callers via
    /api/meetings/public/{slug}. Deliberately excludes
    livekit_room_name, participant emails, recordings, etc."""
    slug: str
    title: str
    status: MeetingStatus
    scheduled_start: datetime | None
    host_name: str | None = None  # display only


class LobbyKnockRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)


class LobbyKnockResponse(BaseModel):
    lobby_id: uuid.UUID
    status: LobbyStatus


class LobbyStatusPollResponse(BaseModel):
    """Guest's polling response. status='waiting' carries no token;
    'admitted' carries a freshly-issued LiveKit token + room name."""
    status: str  # "waiting" | "admitted" | "denied" | "ended"
    token: str | None = None
    room_name: str | None = None
    identity: str | None = None
    record_meeting: bool = False


# ---------------------------------------------------------------------------
# Join token schema
# ---------------------------------------------------------------------------


class GuestJoinRequest(BaseModel):
    guest_name: str = Field(min_length=1, max_length=255)


class JoinTokenResponse(BaseModel):
    token: str
    room_name: str
    identity: str
    # Commit 7 — surface record_meeting so the client hides the manual
    # Record button when server-side Egress is handling recording.
    record_meeting: bool = False
