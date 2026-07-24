"""Add account_subscriptions table (customer pays for their O-Brain plan)

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x0y1z2a3b4c5"
down_revision: Union[str, None] = "w9x0y1z2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_key", sa.String(length=20), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("billing_period", sa.String(length=10), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_account_subscriptions_user_id"),
    )
    op.create_index("ix_account_subscriptions_user_id", "account_subscriptions", ["user_id"])
    op.create_index("ix_account_subscriptions_stripe_customer_id", "account_subscriptions", ["stripe_customer_id"])
    op.create_index("ix_account_subscriptions_stripe_subscription_id", "account_subscriptions", ["stripe_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_account_subscriptions_stripe_subscription_id", table_name="account_subscriptions")
    op.drop_index("ix_account_subscriptions_stripe_customer_id", table_name="account_subscriptions")
    op.drop_index("ix_account_subscriptions_user_id", table_name="account_subscriptions")
    op.drop_table("account_subscriptions")
