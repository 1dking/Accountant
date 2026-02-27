
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class ReminderChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"


class ReminderStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReminderRule(TimestampMixin, Base):
    """User-configurable rule that defines when and how payment reminders are sent."""

    __tablename__ = "reminder_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    days_offset: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Negative = before due, 0 = on due date, positive = after due",
    )
    channel: Mapped[ReminderChannel] = mapped_column(
        Enum(ReminderChannel), nullable=False, default=ReminderChannel.EMAIL,
    )
    email_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sms_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False,
    )


class PaymentReminder(TimestampMixin, Base):
    """Tracks each individual reminder that has been sent (or attempted)."""

    __tablename__ = "payment_reminders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    reminder_rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("reminder_rules.id", ondelete="SET NULL"), nullable=True,
    )
    reminder_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="e.g. 'before_due', 'on_due', 'after_due', 'manual'",
    )
    channel: Mapped[ReminderChannel] = mapped_column(
        Enum(ReminderChannel), nullable=False,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus), nullable=False,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", lazy="selectin")
    contact: Mapped["Contact"] = relationship("Contact", lazy="selectin")
    reminder_rule: Mapped[Optional["ReminderRule"]] = relationship(
        "ReminderRule", lazy="selectin",
    )


# Avoid circular imports
from app.invoicing.models import Invoice  # noqa: E402, F811
from app.contacts.models import Contact  # noqa: E402, F811
