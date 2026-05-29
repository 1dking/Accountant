"""SQLAlchemy models for the meetings module."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
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


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MeetingTemplate(str, enum.Enum):
    """Commit 16 — meeting templates that bias the downstream AI
    pipeline. Affects:
      - record_meeting default at creation time
      - summary prompt (template-specific focus areas)
      - quote draft prompt (skipped entirely for internal syncs)

    Adding a new template? Update:
      1. This enum
      2. TEMPLATE_DEFAULTS in service.py
      3. summary prompt logic in summarization.py
      4. (optional) quote draft skip logic in quote_draft.py
    """
    GENERIC = "generic"               # default — no biases
    DISCOVERY_CALL = "discovery_call" # new-client sales call
    CLIENT_REVIEW = "client_review"   # existing-client periodic review
    INTERNAL_SYNC = "internal_sync"   # team / no recording / no quote


class ParticipantRole(str, enum.Enum):
    HOST = "host"
    PARTICIPANT = "participant"


class LobbyStatus(str, enum.Enum):
    """Commit 8 — Google-Meet-style lobby state for guest participants.

    NULL on the column means the participant was added directly to the
    meeting (host, or pre-Commit-8 row). Guest-knock flow uses the
    other states.
    """
    WAITING = "waiting"   # knocked, host hasn't decided yet
    ADMITTED = "admitted" # host approved; guest poll returns the LK token
    DENIED = "denied"     # host rejected; final terminal state


class RecordingStatus(str, enum.Enum):
    RECORDING = "recording"
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"


class TranscriptStatus(str, enum.Enum):
    """Commit 11 — meeting transcription lifecycle.

    PENDING    — row created, submission to AssemblyAI not yet attempted
    PROCESSING — submitted; AssemblyAI is doing the work; provider_id
                 holds the AssemblyAI transcript id we poll
    AVAILABLE  — completed; full_text + segments_json populated
    FAILED     — terminal error from AssemblyAI; error_message has it
    """
    PENDING = "pending"
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"


class SummaryStatus(str, enum.Enum):
    """Commit 12 — Claude summarization lifecycle. Same shape as
    TranscriptStatus so the UI can render both with one component."""
    PENDING = "pending"
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"


class QuoteDraftStatus(str, enum.Enum):
    """Commit 15 — quote/invoice draft lifecycle.

    PENDING    — row created, Claude call not attempted
    PROCESSING — Claude call in flight
    AVAILABLE  — draft persisted, awaiting host review
    SKIPPED    — Claude determined no scope/pricing was discussed;
                 we keep a row so the scheduler doesn't re-attempt
    REVIEWED   — host clicked Review (audit trail; doesn't send)
    SENT       — host promoted to a real proposal; sent to client
    FAILED     — terminal error; error_message has it
    """
    PENDING = "pending"
    PROCESSING = "processing"
    AVAILABLE = "available"
    SKIPPED = "skipped"
    REVIEWED = "reviewed"
    SENT = "sent"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False
    )
    # Commit 8 — Google-Meet-style shareable shortcode. Unique 11-char
    # form abc-defg-hij. Nullable to keep pre-Commit-8 rows valid until
    # the backfill migration runs; new rows always get a slug.
    slug: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    # Commit 8 — Instant meetings stamp scheduled_start=now(); the
    # column becomes nullable to support legacy/template rows that
    # don't have a planned start.
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    livekit_room_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    record_meeting: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Commit 16 — meeting template biases the downstream AI pipeline.
    # Default is GENERIC for legacy rows; new rows set explicitly via
    # the picker on MeetingsPage.
    template: Mapped[MeetingTemplate] = mapped_column(
        Enum(MeetingTemplate), default=MeetingTemplate.GENERIC, nullable=False,
        server_default=MeetingTemplate.GENERIC.value,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    participants: Mapped[list["MeetingParticipant"]] = relationship(
        "MeetingParticipant", back_populates="meeting", lazy="selectin"
    )
    recordings: Mapped[list["MeetingRecording"]] = relationship(
        "MeetingRecording", back_populates="meeting", lazy="selectin"
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guest_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[ParticipantRole] = mapped_column(
        Enum(ParticipantRole), default=ParticipantRole.PARTICIPANT, nullable=False
    )
    # Commit 8 — Google-Meet-style lobby state. NULL = participant
    # bypasses the lobby (host, or already-in-meeting). The guest-knock
    # endpoint sets WAITING; host admit/deny sets the terminal state.
    lobby_status: Mapped["LobbyStatus | None"] = mapped_column(
        Enum(LobbyStatus), nullable=True
    )
    join_token: Mapped[str | None] = mapped_column(
        String(500), nullable=True, unique=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    meeting: Mapped[Meeting] = relationship(
        "Meeting", back_populates="participants", lazy="selectin"
    )


class MeetingRecording(TimestampMixin, Base):
    __tablename__ = "meeting_recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus), default=RecordingStatus.RECORDING, nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String(128), default="video/mp4", nullable=False
    )
    egress_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    meeting: Mapped[Meeting] = relationship(
        "Meeting", back_populates="recordings", lazy="selectin"
    )


class RecordingTranscript(TimestampMixin, Base):
    """Commit 11 — server-side transcription of a meeting recording.

    Distinct from app/brain/models.py's MeetingTranscript, which is a
    fully-realized AI summary artifact (full_text + summary +
    action_items + financial_commitments) attached to brain memory.
    THIS model tracks the LiveKit-Egress → AssemblyAI pipeline state
    (PENDING/PROCESSING/AVAILABLE/FAILED) for a single recording, and
    holds the raw transcript + segments. A future commit may bridge
    the two (RecordingTranscript.full_text → MeetingTranscript via the
    brain summarizer).

    One row per recording, created when the recording becomes
    AVAILABLE. Submission to AssemblyAI fires asynchronously; a
    scheduler job polls PROCESSING rows for completion every ~2 min.

    AssemblyAI returns utterances with speaker labels (A, B, C, ...) +
    millisecond start/end times; we normalize to seconds and store as
    segments_json. The full_text column will support Postgres FTS in
    Commit 13.
    """
    __tablename__ = "recording_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meeting_recordings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[TranscriptStatus] = mapped_column(
        Enum(TranscriptStatus), default=TranscriptStatus.PENDING, nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), default="assemblyai", nullable=False)
    provider_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MeetingSummary(TimestampMixin, Base):
    """Commit 12 — Claude-generated meeting summary.

    1:1 with RecordingTranscript. Kicked off when the transcript
    becomes AVAILABLE; persisted in chunks (summary_text, decisions,
    topics, action_items). Stored as JSON so the frontend can render
    structured sections without re-parsing.

    Cost tracked via input_tokens/output_tokens for per-meeting
    profitability reporting.
    """
    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recording_transcript_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recording_transcripts.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    status: Mapped[SummaryStatus] = mapped_column(
        Enum(SummaryStatus), default=SummaryStatus.PENDING, nullable=False,
    )
    # The full prose summary (2-3 sentences, surfaced at the top of
    # the UI). Empty/none when status != AVAILABLE.
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[{"text": str, "assignee": str | None, "due_hint": str | None}]
    action_items_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # list[{"topic": str, "decision": str | None}]
    topics_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # list[str] — single-sentence next steps
    next_steps_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Audit + cost trail
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MeetingQuoteDraft(TimestampMixin, Base):
    """Commit 15 — AI-drafted proposal/quote inferred from a meeting.

    Generated AFTER MeetingSummary completes when the transcript +
    summary suggest scope and/or pricing were discussed. NEVER auto-
    sent: the host must explicitly review and promote to a real
    Proposal record (in app/proposals). This is the highest-liability
    surface in the pipeline — a $5,000 quote when the client said
    $500 is a real exposure, so the review gate is mandatory.

    1:1 with MeetingSummary (one draft per AI summary). Confidence
    field surfaces how explicit the discussion was so the host can
    triage: 'high' = exact numbers spoken; 'low' = inferred from
    vague language.
    """
    __tablename__ = "meeting_quote_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meeting_summaries.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    status: Mapped[QuoteDraftStatus] = mapped_column(
        Enum(QuoteDraftStatus), default=QuoteDraftStatus.PENDING, nullable=False,
    )
    # Core draft content — null when status is SKIPPED/PENDING/FAILED.
    draft_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[{"description": str, "quantity": float, "unit_price": float,
    #       "total": float}]
    line_items_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    estimated_total: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'high' / 'medium' / 'low' — how explicit was the discussion.
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Audit + cost trail
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Review trail
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    promoted_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
