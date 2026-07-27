"""telephony least-privilege capability grants

Adds the per-subaccount capability columns to telephony_accounts. Every grant
defaults to FALSE (server_default "0"), so existing subaccounts are DENIED
everything until an operator explicitly turns a capability on — which is the
point of Step 2. That is intentionally a tightening: no tenant is currently
provisioned for billable use, so nothing in service loses access.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

_BOOL_COLS = (
    "allow_voice_outbound",
    "allow_voice_inbound",
    "allow_sms",
    "allow_mms",
    "allow_number_purchase",
    "allow_markup",
)


def upgrade() -> None:
    for col in _BOOL_COLS:
        op.add_column(
            "telephony_accounts",
            sa.Column(col, sa.Boolean(), nullable=False, server_default="0"),
        )
    op.add_column(
        "telephony_accounts", sa.Column("capabilities_updated_by", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "telephony_accounts",
        sa.Column("capabilities_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for col in ("capabilities_updated_at", "capabilities_updated_by", *_BOOL_COLS):
        op.drop_column("telephony_accounts", col)
