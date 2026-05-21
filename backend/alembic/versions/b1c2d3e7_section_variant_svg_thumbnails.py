"""Add svg_thumbnail to section_variants

Revision ID: b1c2d3e7
Revises: b1c2d3e6
Create Date: 2026-05-20

Hand-designed inline SVG schematics for the variant picker cards.
Each schematic is a self-contained vector preview (no external image
hrefs, no remote font loads) using the Liquid Glass palette. The
column is nullable so future variants can be seeded without thumbnails
and fall back to the text-only card.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e7"
down_revision: Union[str, None] = "b1c2d3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "section_variants",
        sa.Column("svg_thumbnail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("section_variants", "svg_thumbnail")
