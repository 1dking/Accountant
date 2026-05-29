"""SQLAlchemy models for the meetings module."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ParticipantRole(str, enum.Enum):
    HOST = "host"
    PARTICIPANT = "participant"


class LobbyStatus(str, enum.Enum):
    """Commit 8 — Google-Meet-style lobby state for guest participants.

    NULL on the column means the participant was added directly to the
    meeting (host, or pre-Commit-8 row). Guest-knock flow uses the
    other states.
    """
    WAITING = "waiting"   # knocked, host hasn't decided yet
    ADMITTED = "admitted" # host approved; guest poll returns the LK token
    DENIED = "denied"     # host rejected; final terminal state


class RecordingStatus(str, enum.Enum):
    RECORDING = "recording"
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False
    )
    # Commit 8 — Google-Meet-style shareable shortcode. Unique 11-char
    # form abc-defg-hij. Nullable to keep pre-Commit-8 rows valid until
    # the backfill migration runs; new rows always get a slug.
    slug: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    # Commit 8 — Instant meetings stamp scheduled_start=now(); the
    # column becomes nullable to support legacy/template rows that
    # don't have a planned start.
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    livekit_room_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    record_meeting: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    participants: Mapped[list["MeetingParticipant"]] = relationship(
        "MeetingParticipant", back_populates="meeting", lazy="selectin"
    )
    recordings: Mapped[list["MeetingRecording"]] = relationship(
        "MeetingRecording", back_populates="meeting", lazy="selectin"
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guest_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[ParticipantRole] = mapped_column(
        Enum(ParticipantRole), default=ParticipantRole.PARTICIPANT, nullable=False
    )
    # Commit 8 — Google-Meet-style lobby state. NULL = participant
    # bypasses the lobby (host, or already-in-meeting). The guest-knock
    # endpoint sets WAITING; host admit/deny sets the terminal state.
    lobby_status: Mapped["LobbyStatus | None"] = mapped_column(
        Enum(LobbyStatus), nullable=True
    )
    join_token: Mapped[str | None] = mapped_column(
        String(500), nullable=True, unique=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    meeting: Mapped[Meeting] = relationship(
        "Meeting", back_populates="participants", lazy="selectin"
    )


class MeetingRecording(TimestampMixin, Base):
    __tablename__ = "meeting_recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus), default=RecordingStatus.RECORDING, nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String(128), default="video/mp4", nullable=False
    )
    egress_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    meeting: Mapped[Meeting] = relationship(
        "Meeting", back_populates="recordings", lazy="selectin"
    )
