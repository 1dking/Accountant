
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class Role(str, enum.Enum):
    """What a user may DO. Which RECORDS they see is ownership + shares; which
    SECTIONS they can open is feature_access_json. Keep the three separate —
    conflating them once shipped a data leak.

    ADMIN        the agency owner. Sees across every employee's section.
    MANAGER      sees their own records plus their direct reports' (manager_id).
                 Same action rights as a TEAM_MEMBER — the extra reach is a
                 VISIBILITY statement, enforced in authorization, not a new set
                 of route permissions.
    TEAM_MEMBER  a normal employee. Owns their own book.
    ACCOUNTANT   same action rights as TEAM_MEMBER; differs only in which modules
                 it gets by default. Effectively a module preset.
    VIEWER       read-only collaborator. Owns nothing, creates nothing, and sees
                 exactly what has been SHARED with it. Seeing nothing by default
                 is intended.
    CLIENT       an outsider. Portal only, scoped to its own contact.
    """

    ADMIN = "admin"
    MANAGER = "manager"
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
    #: Who this employee reports to. A MANAGER sees the records of the users whose
    #: manager_id points at them. One level deep — a manager of managers does not
    #: inherit the whole subtree. SET NULL so removing a manager doesn't delete
    #: their reports.
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cashbook_access: Mapped[str] = mapped_column(
        String(20), default="personal", server_default="personal", nullable=False
    )
    # --- Operator / sub-account tenancy (Phase 2) --------------------------
    #: The sub-account (isolated client tenant) this user belongs to, if any.
    #: NULL = the user lives at the operator/agency level, not inside a client
    #: sub-account. See app/operators/models.py.
    sub_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sub_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Which operator's world this user lives in. The operator's own User row has
    #: operator_id == its own id; their staff and sub-account members carry the
    #: operator's id. NULL = the legacy root tenant (pre-Phase-2 installs), which
    #: keeps existing behaviour: all NULL/NULL users share one tenant.
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: The platform vendor (OCIDM), who sees ACROSS all operators. Distinct from
    #: an operator, who is merely an ADMIN of their own agency. Defaults False so
    #: an operator-admin never gains cross-operator visibility by role alone.
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
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

    # --- MFA (TOTP) ---------------------------------------------------------
    # mfa_secret holds the Fernet-ENCRYPTED base32 TOTP secret; it is only set
    # once enrollment is confirmed. mfa_recovery_codes is a JSON array of
    # SHA-256 hashes (plaintext shown once, never stored). The hard gate before
    # Plaid Link is `mfa_enabled` — see app/auth/mfa_dependencies.py.
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    mfa_secret: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mfa_recovery_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Set when the user's personal data has been irreversibly anonymized under a
    #: verified deletion request (see app/privacy/service.py). The row is kept for
    #: referential integrity + audit legibility; all PII on it is scrubbed.
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
