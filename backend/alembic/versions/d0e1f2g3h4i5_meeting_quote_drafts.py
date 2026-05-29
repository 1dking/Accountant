"""Meeting quote drafts (Commit 15 — AI-drafted proposals)

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2g3h4i5"
down_revision: Union[str, None] = "c9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_quote_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "meeting_id", sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "summary_id", sa.Uuid(),
            sa.ForeignKey("meeting_summaries.id", ondelete="CASCADE"),
            nullable=False, unique=True, index=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("draft_title", sa.String(255), nullable=True),
        sa.Column("draft_summary", sa.Text(), nullable=True),
        sa.Column("line_items_json", sa.JSON(), nullable=True),
        sa.Column("estimated_total", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by", sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "promoted_proposal_id", sa.Uuid(),
            sa.ForeignKey("proposals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("meeting_quote_drafts")
