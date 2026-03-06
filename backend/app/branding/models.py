"""SQLAlchemy models for universal branding settings."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class BrandingSettings(TimestampMixin, Base):
    """Universal branding configuration applied across all touchpoints.

    Singleton pattern — only one row should exist.
    """

    __tablename__ = "branding_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_dark_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(
        String(20), default="#2563eb", server_default="#2563eb"
    )
    secondary_color: Mapped[str] = mapped_column(
        String(20), default="#64748b", server_default="#64748b"
    )
    accent_color: Mapped[str] = mapped_column(
        String(20), default="#f59e0b", server_default="#f59e0b"
    )
    font_heading: Mapped[str] = mapped_column(
        String(100), default="Inter", server_default="Inter"
    )
    font_body: Mapped[str] = mapped_column(
        String(100), default="Inter", server_default="Inter"
    )
    border_radius: Mapped[str] = mapped_column(
        String(20), default="8px", server_default="8px"
    )
    custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_header_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_footer_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    portal_welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_page_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    org_slug: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_branding_updated_by"),
        nullable=False,
    )
