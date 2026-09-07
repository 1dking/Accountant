"""Site catalogue — catalog_items, page_reviews, page_faqs; company/users additive.

Revision ID: m1j2k3l4m5n6
Revises: l0i1b2c3d4e5
Create Date: 2026-09-07

S5 wave 1: the three tables the AI planner and the live-data blocks
(services list, reviews feed, FAQ) fetch from. All new tables are scoped
by `created_by` + `org_id` so the operator channel's sub-accounts get
their own catalogue.

Additive columns:
- company_settings gains site-content fields + a nullable `org_id` (the
  singleton pattern still works; per-owner scoping is opt-in through
  the new pages resolvers).
- users gains public_title, public_bio, avatar_url, show_on_site so the
  team block can pull real content without a separate profile table.

SQLite dev DBs get the same via core/schema_patch.py (additive ALTERs at
boot); this migration is the Postgres path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1j2k3l4m5n6"
down_revision: Union[str, None] = "l0i1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- company_settings additive ---------------------------------------
    with op.batch_alter_table("company_settings") as b:
        b.add_column(sa.Column("org_id", sa.CHAR(32), nullable=True))
        b.add_column(sa.Column("tagline", sa.String(255), nullable=True))
        b.add_column(sa.Column("business_hours_json", sa.Text(), nullable=True))
        b.add_column(sa.Column("google_place_id", sa.String(255), nullable=True))
        b.add_column(sa.Column("service_area_text", sa.String(500), nullable=True))
        b.add_column(sa.Column("map_embed_url", sa.String(1000), nullable=True))
        b.add_column(sa.Column("brand_primary_color", sa.String(9), nullable=True))
        b.add_column(sa.Column("booking_calendar_slug", sa.String(255), nullable=True))
        b.add_column(sa.Column("lead_form_id", sa.CHAR(32), nullable=True))

    # ---- users additive --------------------------------------------------
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("public_title", sa.String(120), nullable=True))
        b.add_column(sa.Column("public_bio", sa.Text(), nullable=True))
        b.add_column(sa.Column("avatar_url", sa.String(500), nullable=True))
        b.add_column(sa.Column("show_on_site", sa.Boolean(), nullable=False, server_default="1"))

    # ---- catalog_items ---------------------------------------------------
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="service"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("price_display", sa.String(50), nullable=True),
        sa.Column("price_period", sa.String(20), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CAD"),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("cta_text", sa.String(60), nullable=True),
        sa.Column("cta_href", sa.String(500), nullable=True),
        sa.Column("stripe_price_id", sa.String(120), nullable=True),
        sa.Column("booking_slug", sa.String(255), nullable=True),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.CHAR(32), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_catalog_items_owner_kind", "catalog_items", ["created_by", "kind", "is_active"])

    # ---- page_reviews ----------------------------------------------------
    op.create_table(
        "page_reviews",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("author_name", sa.String(120), nullable=False),
        sa.Column("author_title", sa.String(120), nullable=True),
        sa.Column("author_avatar_url", sa.String(500), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.CHAR(32), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---- page_faqs -------------------------------------------------------
    op.create_table(
        "page_faqs",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.CHAR(32), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("page_faqs")
    op.drop_table("page_reviews")
    op.drop_index("ix_catalog_items_owner_kind", table_name="catalog_items")
    op.drop_table("catalog_items")
    with op.batch_alter_table("users") as b:
        for col in ("show_on_site", "avatar_url", "public_bio", "public_title"):
            b.drop_column(col)
    with op.batch_alter_table("company_settings") as b:
        for col in ("lead_form_id", "booking_calendar_slug", "brand_primary_color",
                    "map_embed_url", "service_area_text", "google_place_id",
                    "business_hours_json", "tagline", "org_id"):
            b.drop_column(col)
