"""Add voicemail settings columns to users

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("voicemail_greeting_type", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("voicemail_greeting_storage_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("voicemail_greeting_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "voicemail_mode",
            sa.String(length=30),
            nullable=False,
            server_default="cell_then_voicemail",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "voicemail_mode")
    op.drop_column("users", "voicemail_greeting_text")
    op.drop_column("users", "voicemail_greeting_storage_key")
    op.drop_column("users", "voicemail_greeting_type")
