"""Append-only security audit log.

One immutable row per security-relevant event: authentication, MFA, permission
denials, sensitive admin actions, consent capture, and data export/deletion.
Distinct from ``collaboration.ActivityLog`` (product activity) and
``platform_admin.ErrorLog`` (crashes) — this is the demonstrable trail that
Schedule 1 items (consent, deletion, access requests) actually happened.

Immutable by construction: plain ``Base`` (no ``updated_at``), and nothing in
the app exposes an update or delete path for these rows. ``actor_id`` is
``SET NULL`` on user deletion but ``actor_email`` is denormalized so a deleted
actor's actions stay legible — which matters precisely because we now hard-delete
users on request.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    # NB: table is "security_audit_logs" — documents/models.py already owns
    # "audit_logs" (a document-history table). Distinct concerns, distinct tables.
    __tablename__ = "security_audit_logs"
    __table_args__ = (
        Index("ix_security_audit_logs_action_created", "action", "created_at"),
        Index("ix_security_audit_logs_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    #: What happened (see app/audit/service.py AuditAction).
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: "success" | "failure" | "denied".
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")

    #: Who did it. Nulled if the user is later hard-deleted; email is kept.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: Tenant/cohort. Stored as a plain string (not an FK) so it survives
    #: org/user deletion — mirrors app/events/models.py.
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    #: Optional target of the action.
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: Client IP when available (login, MFA, denials).
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: JSON string with event-specific detail (never secrets).
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
