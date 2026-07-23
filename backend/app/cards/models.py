
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class CardEventType(str, enum.Enum):
    """App-level enum backed by a plain string column — deliberately NOT a
    native DB enum, so future event types (wallet_added, nfc_tap) don't
    need an ALTER TYPE migration."""

    VIEW = "view"
    VCARD_DOWNLOAD = "vcard_download"


class BusinessCard(TimestampMixin, Base):
    """A user's public digital business card (Arivio port).

    One card per user. Palette fields are nullable — null means "fall
    back to the org's BrandingSettings color" (resolved server-side in
    the public payload so the public page needs no second fetch).
    """

    __tablename__ = "business_cards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # Mirrors user_id; kept as a separate column so authorization.py's
    # created_by-based ownership helpers work unchanged on this table.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    template: Mapped[str] = mapped_column(String(20), default="classic")  # see schemas.TEMPLATES

    # Identity
    display_name: Mapped[str] = mapped_column(String(255))
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tagline: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_links_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Media
    avatar_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    show_org_logo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Palette (null -> org branding fallback)
    bg_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    button_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    button_text_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    font: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Booking
    scheduling_calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduling_calendars.id", ondelete="SET NULL"), nullable=True
    )
    show_booking: Mapped[bool] = mapped_column(Boolean, default=True)


class CardAnalyticsEvent(Base):
    """Append-only visit log for public card pages (mirrors the pages
    module's dedicated-table precedent, scaled down — no daily rollup;
    card traffic is light enough for live COUNT/COUNT(DISTINCT))."""

    __tablename__ = "card_analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    #: sha256(ip)[:16] — same anonymization as pages/service.py's ip_hash.
    visitor_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
