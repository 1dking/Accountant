"""Meeting summaries (Commit 12 — Claude Sonnet summarization)

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2g3h4"
down_revision: Union[str, None] = "b8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "meeting_id", sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "recording_transcript_id", sa.Uuid(),
            sa.ForeignKey("recording_transcripts.id", ondelete="CASCADE"),
            nullable=False, unique=True, index=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("action_items_json", sa.JSON(), nullable=True),
        sa.Column("topics_json", sa.JSON(), nullable=True),
        sa.Column("next_steps_json", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
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
    op.drop_table("meeting_summaries")
