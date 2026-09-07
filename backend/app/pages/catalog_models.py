"""Site catalogue models — the tables the page builder's data-bound
blocks read from (services, reviews, FAQs).

All three are tenant-scoped by `created_by` (and `org_id` when the row
belongs to an organisation). Nothing in the accounting side touches
them: pages resolvers own the queries, pages catalog_router owns the
CRUD. Deletes are ON CASCADE from users.
"""
from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class CatalogItem(TimestampMixin, Base):
    """A service / product / plan offered on the public site.

    `kind` distinguishes shape:
      service — one-off/hourly work (default; renders in "Services" blocks)
      product — physical goods (renders in "Products" blocks)
      plan    — subscription tier (renders in "Pricing" blocks)

    `price_display` wins over `price_cents` when set (e.g. "From $99",
    "Custom quote"); `price_cents` + `currency` + `price_period` are the
    structured form used by Stripe integrations.
    """

    __tablename__ = "catalog_items"
    __table_args__ = (Index("ix_catalog_items_owner_kind", "created_by", "kind", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="service", server_default="service")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_display: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price_period: Mapped[str | None] = mapped_column(String(20), nullable=True)  # month / year / hour / project
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CAD", server_default="CAD")
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[str]
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cta_text: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cta_href: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    booking_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)


class PageReview(TimestampMixin, Base):
    """A testimonial / review shown on the public site.

    `source` is where it came from (`manual`, `google`, `facebook`, …).
    Google imports (S7) write with source='google' + source_url; the
    reviews-feed block filters on source when the block config asks it to.
    """

    __tablename__ = "page_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    author_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    author_avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5, or NULL
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", server_default="manual")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)


class PageFAQ(TimestampMixin, Base):
    """A frequently-asked question shown on the public site."""

    __tablename__ = "page_faqs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
