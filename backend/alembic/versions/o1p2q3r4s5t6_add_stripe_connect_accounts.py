"""Add stripe_connect_accounts table

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, None] = "n0o1p2q3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_connect_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_account_id", sa.String(length=255), nullable=False),
        sa.Column("charges_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payouts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("details_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("user_id", name="uq_stripe_connect_accounts_user_id"),
        sa.UniqueConstraint("stripe_account_id", name="uq_stripe_connect_accounts_stripe_account_id"),
    )
    op.create_index("ix_stripe_connect_accounts_user_id", "stripe_connect_accounts", ["user_id"])
    op.create_index(
        "ix_stripe_connect_accounts_stripe_account_id", "stripe_connect_accounts", ["stripe_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_connect_accounts_stripe_account_id", table_name="stripe_connect_accounts")
    op.drop_index("ix_stripe_connect_accounts_user_id", table_name="stripe_connect_accounts")
    op.drop_table("stripe_connect_accounts")
