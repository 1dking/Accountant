
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


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
    template: Mapped[str] = mapped_column(String(20), default="classic")  # classic|modern|minimal

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
