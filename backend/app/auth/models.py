
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class Role(str, enum.Enum):
    ADMIN = "admin"
    TEAM_MEMBER = "team_member"
    ACCOUNTANT = "accountant"
    CLIENT = "client"
    VIEWER = "viewer"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="local", server_default="local", nullable=False)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    news_preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_access_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cashbook_access: Mapped[str] = mapped_column(
        String(20), default="personal", server_default="personal", nullable=False
    )
    fallback_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    voicemail_greeting_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    voicemail_greeting_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voicemail_greeting_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    voicemail_mode: Mapped[str] = mapped_column(
        String(30),
        default="cell_then_voicemail",
        server_default="cell_then_voicemail",
        nullable=False,
    )
    booking_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conversation_reply_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    conversation_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_ai_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the engine is on AND inbound comes from an unknown number,
    # AI asks for name+email. Defaults true — only useful when the
    # conversation engine itself is enabled.
    identity_capture_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    # Per-item onboarding metadata: { item_key: { dismissed_at: ISO } }
    onboarding_state: Mapped[dict | None] = mapped_column(
        JSON, nullable=False, server_default="{}", default=dict
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
