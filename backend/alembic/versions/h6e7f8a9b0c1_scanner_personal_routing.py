"""Scanner personal routing: personal back-link + mirror-account key.

Additive only. Adds a back-link on plaid_transactions to a copied
PersonalTransaction, and an external_key on personal_accounts so a shared bank
feed's personal copies land in one mirror account.

Revision ID: h6e7f8a9b0c1
Revises: g5d6e7f8a9b0
"""
import sqlalchemy as sa
from alembic import op

revision = "h6e7f8a9b0c1"
down_revision = "g5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plaid_transactions",
        sa.Column("matched_personal_transaction_id", sa.CHAR(32),
                  sa.ForeignKey("personal_transactions.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "personal_accounts",
        sa.Column("external_key", sa.String(255), nullable=True),
    )
    op.create_index("ix_personal_accounts_external_key", "personal_accounts", ["external_key"])


def downgrade() -> None:
    op.drop_index("ix_personal_accounts_external_key", "personal_accounts")
    op.drop_column("personal_accounts", "external_key")
    op.drop_column("plaid_transactions", "matched_personal_transaction_id")
