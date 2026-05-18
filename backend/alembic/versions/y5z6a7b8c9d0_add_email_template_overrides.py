"""Add email_template_overrides table

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_template_overrides",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_key", sa.String(length=50), nullable=False),
        sa.Column("subject_override", sa.String(length=255), nullable=True),
        sa.Column("body_override", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_email_template_overrides_user_key",
        "email_template_overrides",
        ["user_id", "template_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_template_overrides_user_key",
        table_name="email_template_overrides",
    )
    op.drop_table("email_template_overrides")
