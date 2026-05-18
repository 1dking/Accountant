"""Add password_reset_tokens table

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, None] = "w3x4y5z6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_password_reset_tokens_token",
        "password_reset_tokens",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_user_used",
        "password_reset_tokens",
        ["user_id", "used_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_user_used", table_name="password_reset_tokens"
    )
    op.drop_index(
        "ix_password_reset_tokens_token", table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
