"""Meeting transcripts (Commit 11 — AssemblyAI integration)

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2g3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recording_transcripts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "meeting_id", sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "recording_id", sa.Uuid(),
            sa.ForeignKey("meeting_recordings.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(32), nullable=False, server_default="assemblyai"),
        sa.Column("provider_id", sa.String(64), nullable=True, index=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("segments_json", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
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
    op.drop_table("recording_transcripts")
