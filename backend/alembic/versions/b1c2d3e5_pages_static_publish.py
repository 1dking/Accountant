"""Add static-publish columns to pages

Revision ID: b1c2d3e5
Revises: b1c2d3e4
Create Date: 2026-05-19

Pages v2 — Session 2 (descoped). Stores the compiled static HTML
output of the Sections JSON, the R2 object key it was uploaded to,
and the publish timestamp. The existing live_html_content column
remains for backward compatibility with the legacy opaque-HTML flow.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e5"
down_revision: Union[str, None] = "b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Full compiled HTML doc — Tailwind CDN + JSON-LD + semantic
    # markup + all sections rendered.
    op.add_column(
        "pages",
        sa.Column("compiled_html", sa.Text(), nullable=True),
    )
    # R2 object key (relative to bucket): "pages/{slug}/index.html"
    op.add_column(
        "pages",
        sa.Column(
            "compiled_html_r2_key",
            sa.String(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "pages",
        sa.Column(
            "compiled_html_published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("pages", "compiled_html_published_at")
    op.drop_column("pages", "compiled_html_r2_key")
    op.drop_column("pages", "compiled_html")
