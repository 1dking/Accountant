"""Add identity capture tables + columns

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Flag on sms_messages for AI's "who is this?" outbound messages so the
    # engine knows the next inbound is an identity answer, not a normal reply.
    op.add_column(
        "sms_messages",
        sa.Column(
            "is_identity_capture_attempt",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Per-user toggle for the identity-capture branch of the engine.
    # Default True — if you have the conversation engine on, you probably
    # want unknown numbers to identify themselves.
    op.add_column(
        "users",
        sa.Column(
            "identity_capture_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # State table for the identity capture flow. One row per
    # (phone_number, user_id) pair — tracks attempts + outcome.
    op.create_table(
        "identity_capture_attempts",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_name", sa.String(length=255), nullable=True),
        sa.Column("extracted_email", sa.String(length=255), nullable=True),
        # contact_created_id is logical FK — SQLite ALTER constraint limits
        sa.Column("contact_created_id", sa.CHAR(32), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_identity_capture_phone_user",
        "identity_capture_attempts",
        ["phone_number", "user_id"],
        unique=True,
    )
    op.create_index(
        "ix_identity_capture_user_recent",
        "identity_capture_attempts",
        ["user_id", "last_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_identity_capture_user_recent", table_name="identity_capture_attempts")
    op.drop_index("ix_identity_capture_phone_user", table_name="identity_capture_attempts")
    op.drop_table("identity_capture_attempts")
    op.drop_column("users", "identity_capture_enabled")
    op.drop_column("sms_messages", "is_identity_capture_attempt")
