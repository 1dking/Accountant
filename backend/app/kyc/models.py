"""KYC Verification models."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KycStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class KycVerification(Base):
    __tablename__ = "kyc_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[KycStatus] = mapped_column(default=KycStatus.NOT_STARTED)

    # Business info
    business_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Personal info
    full_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    personal_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    government_id_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    government_id_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Admin review
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
