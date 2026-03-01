import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class ResourceType(str, enum.Enum):
    ESTIMATE = "estimate"
    INVOICE = "invoice"


class PublicAccessToken(TimestampMixin, Base):
    __tablename__ = "public_access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
