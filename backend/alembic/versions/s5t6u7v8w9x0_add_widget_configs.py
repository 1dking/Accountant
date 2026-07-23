"""Add widget_configs table (embeddable lead-capture widget, Arivio port)

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s5t6u7v8w9x0"
down_revision: Union[str, None] = "r4s5t6u7v8w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "widget_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("widget_key", sa.String(length=64), nullable=False),
        sa.Column("form_id", sa.Uuid(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="floating"),
        sa.Column("position", sa.String(length=20), nullable=False, server_default="bottom-right"),
        sa.Column("button_color", sa.String(length=20), nullable=True),
        sa.Column("bg_color", sa.String(length=20), nullable=True),
        sa.Column("text_color", sa.String(length=20), nullable=True),
        sa.Column("greeting_title", sa.String(length=255), nullable=True),
        sa.Column("greeting_message", sa.Text(), nullable=True),
        sa.Column("success_message", sa.Text(), nullable=True),
        sa.Column("collect_phone", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_widget_configs_user_id"),
        sa.UniqueConstraint("widget_key", name="uq_widget_configs_widget_key"),
    )
    op.create_index("ix_widget_configs_user_id", "widget_configs", ["user_id"])
    op.create_index("ix_widget_configs_widget_key", "widget_configs", ["widget_key"])


def downgrade() -> None:
    op.drop_index("ix_widget_configs_widget_key", table_name="widget_configs")
    op.drop_index("ix_widget_configs_user_id", table_name="widget_configs")
    op.drop_table("widget_configs")
