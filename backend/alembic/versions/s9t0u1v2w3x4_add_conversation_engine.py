"""Add conversation engine columns

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sms_messages: flag for AI-auto-replies (loop guard + analytics)
    op.add_column(
        "sms_messages",
        sa.Column(
            "is_auto_reply",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # users: global toggle + template + AI tone instructions
    op.add_column(
        "users",
        sa.Column(
            "conversation_reply_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("conversation_template", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("conversation_ai_instructions", sa.Text(), nullable=True),
    )

    # contacts: per-conversation kill switch + paused flag (when user
    # manually replies, AI steps back for this contact)
    op.add_column(
        "contacts",
        sa.Column("conversation_engine_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column(
            "conversation_engine_paused_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("contacts", "conversation_engine_paused_until")
    op.drop_column("contacts", "conversation_engine_enabled")
    op.drop_column("users", "conversation_ai_instructions")
    op.drop_column("users", "conversation_template")
    op.drop_column("users", "conversation_reply_enabled")
    op.drop_column("sms_messages", "is_auto_reply")
