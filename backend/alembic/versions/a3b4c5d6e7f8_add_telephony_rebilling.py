"""Add telephony rebilling: rate card, prepaid credits, ledger, A2P registration

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-07-24

Money is stored as INTEGER MICRO-DOLLARS (1e-6 USD). Telephony rates are
fractions of a cent, so floats would drift across millions of small debits.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "z2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telephony_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False, server_default="global"),
        sa.Column("scope_key", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("our_cost_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sell_price_micros", sa.Integer(), nullable=True),
        sa.Column("markup_multiplier", sa.Float(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "scope_key", "unit", name="uq_telephony_rate_scope_unit"),
    )
    op.create_index("ix_telephony_rates_scope_key", "telephony_rates", ["scope_key"])
    op.create_index("ix_telephony_rates_unit", "telephony_rates", ["unit"])

    op.create_table(
        "telephony_credits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("balance_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_purchased_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_spent_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_topup_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("auto_topup_threshold_micros", sa.Integer(), nullable=True),
        sa.Column("auto_topup_amount_micros", sa.Integer(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_method_id", sa.String(length=255), nullable=True),
        sa.Column("last_topup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("low_balance_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_key", name="uq_telephony_credits_tenant"),
    )
    op.create_index("ix_telephony_credits_tenant_key", "telephony_credits", ["tenant_key"])
    op.create_index("ix_telephony_credits_owner", "telephony_credits", ["owner_user_id"])

    op.create_table(
        "telephony_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("our_cost_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billed_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_after_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # UNIQUE is the idempotency guarantee: re-running the metering job can
        # never double-bill the same Twilio usage record.
        sa.UniqueConstraint("external_ref", name="uq_telephony_ledger_external_ref"),
    )
    op.create_index("ix_telephony_ledger_tenant_key", "telephony_ledger", ["tenant_key"])
    op.create_index("ix_telephony_ledger_period", "telephony_ledger", ["period"])
    op.create_index("ix_telephony_ledger_entry_type", "telephony_ledger", ["entry_type"])
    op.create_index("ix_telephony_ledger_tenant_period", "telephony_ledger", ["tenant_key", "period"])

    op.create_table(
        "a2p_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="not_started"),
        sa.Column("business_name", sa.String(length=255), nullable=True),
        sa.Column("business_type", sa.String(length=64), nullable=True),
        sa.Column("ein", sa.String(length=32), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("address_json", sa.Text(), nullable=True),
        sa.Column("use_case", sa.String(length=64), nullable=True),
        sa.Column("sample_messages_json", sa.Text(), nullable=True),
        sa.Column("profile_sid", sa.String(length=64), nullable=True),
        sa.Column("brand_sid", sa.String(length=64), nullable=True),
        sa.Column("campaign_sid", sa.String(length=64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_key", name="uq_a2p_registrations_tenant"),
    )
    op.create_index("ix_a2p_registrations_tenant_key", "a2p_registrations", ["tenant_key"])
    op.create_index("ix_a2p_registrations_owner", "a2p_registrations", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_a2p_registrations_owner", table_name="a2p_registrations")
    op.drop_index("ix_a2p_registrations_tenant_key", table_name="a2p_registrations")
    op.drop_table("a2p_registrations")
    for ix in (
        "ix_telephony_ledger_tenant_period",
        "ix_telephony_ledger_entry_type",
        "ix_telephony_ledger_period",
        "ix_telephony_ledger_tenant_key",
    ):
        op.drop_index(ix, table_name="telephony_ledger")
    op.drop_table("telephony_ledger")
    op.drop_index("ix_telephony_credits_owner", table_name="telephony_credits")
    op.drop_index("ix_telephony_credits_tenant_key", table_name="telephony_credits")
    op.drop_table("telephony_credits")
    op.drop_index("ix_telephony_rates_unit", table_name="telephony_rates")
    op.drop_index("ix_telephony_rates_scope_key", table_name="telephony_rates")
    op.drop_table("telephony_rates")
