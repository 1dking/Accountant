
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class MatchField(str, enum.Enum):
    NAME = "name"
    MERCHANT_NAME = "merchant_name"
    CATEGORY = "category"


class MatchType(str, enum.Enum):
    CONTAINS = "contains"
    EXACT = "exact"
    STARTS_WITH = "starts_with"
    REGEX = "regex"


class CategorizationRule(TimestampMixin, Base):
    __tablename__ = "categorization_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_field: Mapped[MatchField] = mapped_column(Enum(MatchField), nullable=False)
    match_type: Mapped[MatchType] = mapped_column(Enum(MatchType), nullable=False)
    match_value: Mapped[str] = mapped_column(String(500), nullable=False)
    assign_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
