"""Add section_variants table (Pages v2 — variant library)

Revision ID: b1c2d3e6
Revises: b1c2d3e5
Create Date: 2026-05-19

The variant library backs the "Change variant" / "+ Add Section"
picker in SectionEditor. Each row is a Tailwind-rendered template
parameterized with {{TOKEN}} placeholders that get substituted with
the section's default_props (or migrated content from a previous
variant's edited_html where placeholder names match).

Seeded variants are committed via a separate seed script run from
the application — keeping seed data out of the migration so we can
re-seed without rolling versions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e6"
down_revision: Union[str, None] = "b1c2d3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "section_variants",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("variant_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("jsx_template", sa.Text(), nullable=False),
        sa.Column("default_props", sa.Text(), nullable=False),  # JSON blob
        sa.Column("preview_thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("category", "variant_id", name="uq_section_variants_category_variant_id"),
    )
    op.create_index("ix_section_variants_category", "section_variants", ["category"])


def downgrade() -> None:
    op.drop_index("ix_section_variants_category", table_name="section_variants")
    op.drop_table("section_variants")
