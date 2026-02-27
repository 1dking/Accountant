
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class EstimateStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONVERTED = "converted"


class Estimate(TimestampMixin, Base):
    __tablename__ = "estimates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[EstimateStatus] = mapped_column(
        Enum(EstimateStatus), default=EstimateStatus.DRAFT, nullable=False
    )
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tax_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", lazy="selectin")
    line_items: Mapped[list["EstimateLineItem"]] = relationship(
        "EstimateLineItem", back_populates="estimate", lazy="selectin", cascade="all, delete-orphan"
    )


# Avoid circular import — Contact is defined in contacts module
from app.contacts.models import Contact  # noqa: E402, F811


class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float] = mapped_column(Float, nullable=False)

    estimate: Mapped[Estimate] = relationship("Estimate", back_populates="line_items")
