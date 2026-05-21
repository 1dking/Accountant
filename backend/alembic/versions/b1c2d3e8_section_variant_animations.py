"""Add default_animations to section_variants

Revision ID: b1c2d3e8
Revises: b1c2d3e7
Create Date: 2026-05-21

Per-variant animation defaults (Commit 4). JSON blob describing the
GSAP/ScrollTrigger timelines to apply on the compiled page:

  {
    "scroll_reveal": [
      {"selector": "h1", "from": {"y": 40, "opacity": 0},
       "to": {"y": 0, "opacity": 1},
       "duration": 0.8, "ease": "power2.out", "delay": 0, "stagger": 0}
    ],
    "counter_up": [
      {"selector": ".stat-number", "duration": 1.5, "ease": "power2.out"}
    ]
  }

variant_to_section() snapshots this into sections_json[i].animations
at insert time — same pattern as metadata.props. compile_page reads
the per-section snapshot; for legacy sections without one, the router
passes a variants_map fallback dict.

Nullable so future variants without animations work fine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e8"
down_revision: Union[str, None] = "b1c2d3e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "section_variants",
        sa.Column("default_animations", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("section_variants", "default_animations")
