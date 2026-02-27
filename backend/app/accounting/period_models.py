"""SQLAlchemy models for accounting period closing/locking."""


import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class PeriodStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class AccountingPeriod(TimestampMixin, Base):
    __tablename__ = "accounting_periods"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus), default=PeriodStatus.OPEN, nullable=False
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
