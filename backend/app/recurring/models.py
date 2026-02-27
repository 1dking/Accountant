
import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class RecurringType(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"
    INVOICE = "invoice"


class Frequency(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class RecurringRule(TimestampMixin, Base):
    __tablename__ = "recurring_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[RecurringType] = mapped_column(Enum(RecurringType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[Frequency] = mapped_column(Enum(Frequency), nullable=False)
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    template_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    last_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
