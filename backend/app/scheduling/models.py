"""SQLAlchemy models for the native calendar & scheduling module."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class CalendarType(str, enum.Enum):
    PERSONAL = "personal"
    TEAM = "team"
    ROUND_ROBIN = "round_robin"


class MeetingType(str, enum.Enum):
    PHONE = "phone"
    VIDEO = "video"
    IN_PERSON = "in_person"


class SchedulingCalendar(TimestampMixin, Base):
    """A booking calendar that can be shared publicly."""

    __tablename__ = "scheduling_calendars"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_type: Mapped[CalendarType] = mapped_column(
        Enum(CalendarType), default=CalendarType.PERSONAL, nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_advance_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    min_notice_hours: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    availability_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    google_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    members: Mapped[list["CalendarMember"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["CalendarBooking"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )


class CalendarMember(TimestampMixin, Base):
    """Users assigned to a scheduling calendar (for round-robin / team)."""

    __tablename__ = "calendar_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "scheduling_calendars.id",
            ondelete="CASCADE",
            name="fk_calendar_members_calendar",
        ),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_calendar_members_user"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    calendar: Mapped["SchedulingCalendar"] = relationship(back_populates="members")


class CalendarBooking(TimestampMixin, Base):
    """A booking / appointment made against a scheduling calendar."""

    __tablename__ = "calendar_bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "scheduling_calendars.id",
            ondelete="CASCADE",
            name="fk_calendar_bookings_calendar",
        ),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "contacts.id",
            ondelete="SET NULL",
            name="fk_calendar_bookings_contact",
        ),
        nullable=True,
        index=True,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_calendar_bookings_assigned_user",
        ),
        nullable=True,
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    guest_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guest_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_type: Mapped[MeetingType | None] = mapped_column(
        Enum(MeetingType), nullable=True
    )
    meeting_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reschedule_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    cancel_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_1h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    calendar: Mapped["SchedulingCalendar"] = relationship(back_populates="bookings")
