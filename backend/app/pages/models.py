"""SQLAlchemy models for the AI page builder module."""

import datetime as _dt
import enum
import uuid

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
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


# ── Website (multi-page container) ──────────────────────────────────────


class Website(TimestampMixin, Base):
    """A multi-page website that groups several pages together."""

    __tablename__ = "websites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    global_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    nav_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_defaults_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking_pixels_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    pages: Mapped[list["Page"]] = relationship(
        back_populates="website", cascade="all, delete-orphan",
        foreign_keys="Page.website_id",
    )


# ── Page ────────────────────────────────────────────────────────────────


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
    tracking_pixels_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_history_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Website FK (nullable — standalone pages have no website)
    website_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE", name="fk_pages_website"),
        nullable=True,
        index=True,
    )
    page_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    website: Mapped["Website | None"] = relationship(
        back_populates="pages", foreign_keys=[website_id]
    )
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


# ── Visitor-level analytics ─────────────────────────────────────────────


class PageVisit(Base):
    """Individual page visit with full context."""

    __tablename__ = "page_visits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    website_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("websites.id", ondelete="SET NULL"), nullable=True,
    )
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class PageEvent(Base):
    """Individual analytics event (scroll, click, etc.)."""

    __tablename__ = "page_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("page_visits.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class TemplateScope(str, enum.Enum):
    ORG = "org"
    PLATFORM = "platform"


class PageTemplate(TimestampMixin, Base):
    """Reusable page template (org-level or platform-wide)."""

    __tablename__ = "page_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    css_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[TemplateScope] = mapped_column(
        Enum(TemplateScope), default=TemplateScope.ORG, nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )


class PageAnalyticsDaily(Base):
    """Pre-aggregated daily analytics for fast dashboard queries."""

    __tablename__ = "page_analytics_daily"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    date: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    visitors: Mapped[int] = mapped_column(Integer, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    page_views: Mapped[int] = mapped_column(Integer, default=0)
    avg_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    bounce_count: Mapped[int] = mapped_column(Integer, default=0)
    scroll_25_count: Mapped[int] = mapped_column(Integer, default=0)
    scroll_50_count: Mapped[int] = mapped_column(Integer, default=0)
    scroll_75_count: Mapped[int] = mapped_column(Integer, default=0)
    scroll_100_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    form_submit_count: Mapped[int] = mapped_column(Integer, default=0)
