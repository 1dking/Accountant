"""SQLAlchemy models for O-Brain AI — knowledge base, conversations, transcripts, alerts."""

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EmbeddingSourceType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    CALL_TRANSCRIPT = "call_transcript"
    MEETING_TRANSCRIPT = "meeting_transcript"
    CALL_NOTES = "call_notes"
    MEETING_NOTES = "meeting_notes"
    DOCUMENT = "document"
    BRAND_KNOWLEDGE = "brand_knowledge"
    MANUAL_NOTE = "manual_note"
    FORM_RESPONSE = "form_response"
    INTERNAL_COMMENT = "internal_comment"


class TranscriptionStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class AlertType(str, enum.Enum):
    OVERDUE_INVOICE = "overdue_invoice"
    UNSIGNED_PROPOSAL = "unsigned_proposal"
    TAX_DEADLINE = "tax_deadline"
    EXPENSE_ANOMALY = "expense_anomaly"
    REVENUE_MILESTONE = "revenue_milestone"
    STALE_CONTACTS = "stale_contacts"
    UNRESPONDED_MESSAGES = "unresponded_messages"
    UPCOMING_RENEWAL = "upcoming_renewal"
    UNACTIONED_COMMITMENT = "unactioned_commitment"
    FINANCIAL_COMMITMENT = "financial_commitment"
    UPCOMING_DEADLINE = "upcoming_deadline"
    FOLLOW_UP_NEEDED = "follow_up_needed"
    CASHFLOW_WARNING = "cashflow_warning"


class AuditActionType(str, enum.Enum):
    EXPENSE_CATEGORIZATION = "expense_categorization"
    RECEIPT_IMPORT = "receipt_import"
    MEETING_SUMMARY = "meeting_summary"
    FINANCIAL_COMMITMENT_DETECTION = "financial_commitment_detection"
    WORKFLOW_AI_ACTION = "workflow_ai_action"
    PROACTIVE_ALERT = "proactive_alert"
    CHAT_QUERY = "chat_query"


# ---------------------------------------------------------------------------
# Brain Embeddings (vector store)
# ---------------------------------------------------------------------------

class BrainEmbedding(TimestampMixin, Base):
    """Vector embeddings for unstructured content search."""

    __tablename__ = "brain_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_brain_emb_user"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as JSON array of floats (pgvector column added via raw SQL in migration)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[EmbeddingSourceType] = mapped_column(
        Enum(EmbeddingSourceType), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL", name="fk_brain_emb_contact"),
        nullable=True,
    )
    relevance_weight: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_brain_emb_user_source", "user_id", "source_type"),
        Index("ix_brain_emb_contact", "contact_id"),
        Index("ix_brain_emb_source_id", "source_id"),
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class BrainConversation(TimestampMixin, Base):
    """Persistent O-Brain chat conversations."""

    __tablename__ = "brain_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_brain_conv_user"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), default="New conversation")

    messages: Mapped[list["BrainMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="BrainMessage.created_at",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_brain_conv_user", "user_id"),
    )


class BrainMessage(TimestampMixin, Base):
    """Individual messages in a Brain conversation."""

    __tablename__ = "brain_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brain_conversations.id", ondelete="CASCADE", name="fk_brain_msg_conv"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_cited_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["BrainConversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_brain_msg_conv", "conversation_id"),
    )


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

class MeetingTranscript(TimestampMixin, Base):
    """Transcription of a meeting recording."""

    __tablename__ = "meeting_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE", name="fk_mt_meeting"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_mt_user"),
        nullable=False,
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    speakers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_commitments_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_mt_meeting", "meeting_id"),
    )


class CallTranscript(TimestampMixin, Base):
    """Transcription of a phone call recording."""

    __tablename__ = "call_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    call_sid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_ct_user"),
        nullable=False,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL", name="fk_ct_contact"),
        nullable=True,
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    speakers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_commitments_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_ct_user", "user_id"),
        Index("ix_ct_contact", "contact_id"),
    )


# ---------------------------------------------------------------------------
# Transcription queue
# ---------------------------------------------------------------------------

class TranscriptionQueueItem(TimestampMixin, Base):
    """Queue item for async transcription processing."""

    __tablename__ = "transcription_queue"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_tq_user"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # meeting | call
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    recording_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[TranscriptionStatus] = mapped_column(
        Enum(TranscriptionStatus), default=TranscriptionStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_tq_status", "status"),
        Index("ix_tq_user", "user_id"),
    )


# ---------------------------------------------------------------------------
# Proactive alerts
# ---------------------------------------------------------------------------

class ProactiveAlert(TimestampMixin, Base):
    """Proactive insights generated by daily background job."""

    __tablename__ = "proactive_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_pa_user"),
        nullable=False,
    )
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_pa_user_read", "user_id", "is_read"),
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class BrainAuditLog(TimestampMixin, Base):
    """Audit trail for every AI-assisted action."""

    __tablename__ = "brain_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_bal_user"),
        nullable=False,
    )
    action_type: Mapped[AuditActionType] = mapped_column(
        Enum(AuditActionType), nullable=False
    )
    ai_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_bal_user_action", "user_id", "action_type"),
    )
