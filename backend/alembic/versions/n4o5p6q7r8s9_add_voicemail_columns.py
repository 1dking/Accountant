"""Add voicemail columns to call_logs

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "call_logs",
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default="call",
        ),
    )
    op.add_column(
        "call_logs",
        sa.Column("voicemail_transcript", sa.Text(), nullable=True),
    )
    op.add_column(
        "call_logs",
        sa.Column(
            "voicemail_transcript_status",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("call_logs", "voicemail_transcript_status")
    op.drop_column("call_logs", "voicemail_transcript")
    op.drop_column("call_logs", "kind")
