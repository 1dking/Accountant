"""Add ai_usage meter + telephony_accounts (Twilio subaccount per tenant)

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z2a3b4c5d6e7"
down_revision: Union[str, None] = "y1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "period", name="uq_ai_usage_tenant_period"),
    )
    op.create_index("ix_ai_usage_tenant_key", "ai_usage", ["tenant_key"])
    op.create_index("ix_ai_usage_period", "ai_usage", ["period"])

    op.create_table(
        "telephony_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("subaccount_sid", sa.String(length=64), nullable=False),
        sa.Column("encrypted_auth_token", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_reason", sa.String(length=255), nullable=True),
        sa.Column("max_numbers", sa.Integer(), nullable=True),
        sa.Column("daily_spend_cap_usd", sa.Float(), nullable=True),
        sa.Column("monthly_spend_cap_usd", sa.Float(), nullable=True),
        sa.Column("geo_permissions_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_key", name="uq_telephony_accounts_tenant"),
        sa.UniqueConstraint("subaccount_sid", name="uq_telephony_accounts_sid"),
    )
    op.create_index("ix_telephony_accounts_tenant_key", "telephony_accounts", ["tenant_key"])
    op.create_index("ix_telephony_accounts_owner", "telephony_accounts", ["owner_user_id"])
    op.create_index("ix_telephony_accounts_sid", "telephony_accounts", ["subaccount_sid"])

    # Existing numbers were bought on the PARENT account and have no tenant.
    # Nullable on purpose: NULL means "legacy, still on the parent account",
    # which the migration helper in telephony/service.py reassigns.
    op.add_column(
        "twilio_phone_numbers",
        sa.Column("tenant_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "twilio_phone_numbers",
        sa.Column("subaccount_sid", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_twilio_numbers_tenant_key", "twilio_phone_numbers", ["tenant_key"])


def downgrade() -> None:
    op.drop_index("ix_twilio_numbers_tenant_key", table_name="twilio_phone_numbers")
    op.drop_column("twilio_phone_numbers", "subaccount_sid")
    op.drop_column("twilio_phone_numbers", "tenant_key")
    op.drop_index("ix_telephony_accounts_sid", table_name="telephony_accounts")
    op.drop_index("ix_telephony_accounts_owner", table_name="telephony_accounts")
    op.drop_index("ix_telephony_accounts_tenant_key", table_name="telephony_accounts")
    op.drop_table("telephony_accounts")
    op.drop_index("ix_ai_usage_period", table_name="ai_usage")
    op.drop_index("ix_ai_usage_tenant_key", table_name="ai_usage")
    op.drop_table("ai_usage")
