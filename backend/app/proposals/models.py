
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProposalStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    WAITING_SIGNATURE = "waiting_signature"
    SIGNED = "signed"
    DECLINED = "declined"
    PAID = "paid"


class PaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PROCESSING = "processing"
    PAID = "paid"


class SyncDirection(str, enum.Enum):
    PUSH = "push"
    PULL = "pull"


class SyncStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ProposalTemplate(TimestampMixin, Base):
    __tablename__ = "proposal_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class Proposal(TimestampMixin, Base):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus), default=ProposalStatus.DRAFT, nullable=False
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proposal_templates.id", ondelete="SET NULL"), nullable=True
    )

    # Payment fields
    collect_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_status: Mapped[PaymentStatus | None] = mapped_column(
        Enum(PaymentStatus), nullable=True
    )

    # Public sharing
    public_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Lifecycle timestamps
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Follow-up settings
    follow_up_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", lazy="selectin")
    recipients: Mapped[list["ProposalRecipient"]] = relationship(
        "ProposalRecipient", back_populates="proposal", lazy="selectin", cascade="all, delete-orphan"
    )
    activities: Mapped[list["ProposalActivity"]] = relationship(
        "ProposalActivity", back_populates="proposal", lazy="selectin", cascade="all, delete-orphan"
    )
    template: Mapped["ProposalTemplate | None"] = relationship("ProposalTemplate", lazy="selectin")


# Avoid circular import — Contact is defined in contacts module
from app.contacts.models import Contact  # noqa: E402, F811


class ProposalRecipient(Base):
    __tablename__ = "proposal_recipients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="signer", nullable=False)
    signing_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    signing_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )

    # Signature capture
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Audit fields
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    proposal: Mapped[Proposal] = relationship("Proposal", back_populates="recipients")


class ProposalActivity(Base):
    __tablename__ = "proposal_activities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Audit fields
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    proposal: Mapped[Proposal] = relationship("Proposal", back_populates="activities")


class GhlSyncLog(Base):
    __tablename__ = "ghl_sync_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    ghl_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direction: Mapped[SyncDirection] = mapped_column(Enum(SyncDirection), nullable=False)
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class FollowUpRule(TimestampMixin, Base):
    __tablename__ = "follow_up_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
