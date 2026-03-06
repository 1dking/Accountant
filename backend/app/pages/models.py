"""SQLAlchemy models for the AI page builder module."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class PageStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SectionType(str, enum.Enum):
    HERO = "hero"
    FEATURES = "features"
    PRICING = "pricing"
    TESTIMONIALS = "testimonials"
    CTA = "cta"
    FAQ = "faq"
    ABOUT = "about"
    CONTACT_FORM = "contact_form"
    GALLERY = "gallery"
    STATS = "stats"
    TEAM = "team"
    FOOTER = "footer"
    HEADER = "header"
    CUSTOM_HTML = "custom_html"


class Page(TimestampMixin, Base):
    """Landing page / website page built with AI."""

    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PageStatus] = mapped_column(
        Enum(PageStatus), default=PageStatus.DRAFT, nullable=False
    )
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    css_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    js_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_homepage: Mapped[bool] = mapped_column(Boolean, default=False)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_head_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_preset: Mapped[str | None] = mapped_column(String(50), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    versions: Mapped[list["PageVersion"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    analytics: Mapped[list["PageAnalytic"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class PageVersion(TimestampMixin, Base):
    """Versioned snapshot of a page for history/rollback."""

    __tablename__ = "page_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE", name="fk_page_versions_page"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    css_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    js_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    page: Mapped["Page"] = relationship(back_populates="versions")


class PageAnalytic(TimestampMixin, Base):
    """Analytics event for a page view or form submission."""

    __tablename__ = "page_analytics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE", name="fk_page_analytics_page"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    visitor_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    page: Mapped["Page"] = relationship(back_populates="analytics")
