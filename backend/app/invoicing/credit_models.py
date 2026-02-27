"""SQLAlchemy models for credit notes and refunds."""


import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class CreditNoteStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"


class CreditNote(TimestampMixin, Base):
    __tablename__ = "credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    credit_note_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus), default=CreditNoteStatus.DRAFT, nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", lazy="selectin")
    contact: Mapped["Contact"] = relationship("Contact", lazy="selectin")


# Avoid circular imports
from app.invoicing.models import Invoice  # noqa: E402, F811
from app.contacts.models import Contact  # noqa: E402, F811
