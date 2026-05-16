"""Add recording + Twilio call SID columns to call_logs

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("call_logs", sa.Column("twilio_call_sid", sa.String(length=50), nullable=True))
    op.add_column("call_logs", sa.Column("recording_sid", sa.String(length=50), nullable=True))
    op.add_column("call_logs", sa.Column("recording_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("call_logs", sa.Column("recording_status", sa.String(length=20), nullable=True))
    op.create_index(
        "ix_call_logs_twilio_call_sid",
        "call_logs",
        ["twilio_call_sid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_call_logs_twilio_call_sid", table_name="call_logs")
    op.drop_column("call_logs", "recording_status")
    op.drop_column("call_logs", "recording_duration_seconds")
    op.drop_column("call_logs", "recording_sid")
    op.drop_column("call_logs", "twilio_call_sid")
