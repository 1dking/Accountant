"""Append-only product-event log, per OBRAIN_EVENT_SPEC.md §1.

One row per event; the envelope (event/org_id/timestamp/properties) is fixed,
`properties_json` carries the event-specific payload. This feeds the Pricing
Lab's OBrainAdapter — it is a reporting log, not a queue, and nothing reads it
synchronously in the request path that wrote it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Deliberately plain Base, not TimestampMixin — event rows are immutable
# facts about the past (mirrors ContactActivity's choice for the same reason).


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_events_dedupe_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Cohort/grouping key. See app/events/service.py::resolve_org_id — this app
    # is owner-private by default (no enforced multi-tenancy), so most
    # deployments have exactly one cohort: the admin/owner's user id, used as a
    # stand-in org id when User.org_id is unset.
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    properties_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # sha256(event|org_id|timestamp|properties) — enforces the spec's
    # at-least-once-tolerant dedupe at the DB level, not just in the adapter.
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
