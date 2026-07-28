"""bank scanner: link payment accounts to Plaid, transactions to Cashbook

Two additive, nullable columns that let a synced bank transaction be posted to
the Cashbook against an auto-provisioned account:

  * payment_accounts.plaid_account_id       — the Plaid account this payment
    account mirrors (indexed; get_or_create_bank_account looks it up).
  * plaid_transactions.matched_cashbook_entry_id — the Cashbook entry a synced
    transaction was posted to (mirrors matched_expense_id/matched_income_id).

Both nullable — existing rows are simply NULL, so this is a pure additive
change with no backfill. (The SQLite production DB gets these via
app/core/schema_patch.py on boot; this migration is the Postgres path.)

Revision ID: f3b4c5d6e7a8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op

revision = "f3b4c5d6e7a8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_accounts",
        sa.Column("plaid_account_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_payment_accounts_plaid_account_id",
        "payment_accounts",
        ["plaid_account_id"],
    )
    op.add_column(
        "plaid_transactions",
        sa.Column("matched_cashbook_entry_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_plaid_transactions_matched_cashbook_entry_id",
        "plaid_transactions",
        "cashbook_entries",
        ["matched_cashbook_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_plaid_transactions_matched_cashbook_entry_id",
        "plaid_transactions",
        type_="foreignkey",
    )
    op.drop_column("plaid_transactions", "matched_cashbook_entry_id")
    op.drop_index(
        "ix_payment_accounts_plaid_account_id",
        table_name="payment_accounts",
    )
    op.drop_column("payment_accounts", "plaid_account_id")
