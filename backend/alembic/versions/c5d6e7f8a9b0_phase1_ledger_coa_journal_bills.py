"""Phase 1 — Chart of Accounts, journal entries, vendor bills; CoA mapping cols

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-24

The double-entry ledger spine. Money is Numeric(14,2) USD. All tables are
tenant-scoped (user_id + org_id); account numbers unique PER TENANT.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCT_TYPE = sa.Enum("ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE", name="accounttype_coa")
_JE_STATUS = sa.Enum("POSTED", "VOID", name="journalentrystatus")
_BILL_STATUS = sa.Enum("DRAFT", "PENDING", "APPROVED", "PAID", "VOID", name="billstatus")


def upgrade() -> None:
    bind = op.get_bind()
    # Native enums need explicit creation on Postgres; SQLite inlines them.
    if bind.dialect.name == "postgresql":
        _ACCT_TYPE.create(bind, checkfirst=True)
        _JE_STATUS.create(bind, checkfirst=True)
        _BILL_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "chart_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_type", _ACCT_TYPE, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["chart_accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "org_id", "code", name="uq_chart_account_tenant_code"),
    )
    op.create_index("ix_chart_accounts_user_id", "chart_accounts", ["user_id"])
    op.create_index("ix_chart_accounts_org_id", "chart_accounts", ["org_id"])
    op.create_index("ix_chart_accounts_code", "chart_accounts", ["code"])
    op.create_index("ix_chart_accounts_tenant_type", "chart_accounts", ["user_id", "account_type"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("status", _JE_STATUS, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("user_id", "org_id", "entry_number", name="uq_journal_entry_tenant_number"),
    )
    op.create_index("ix_journal_entries_user_id", "journal_entries", ["user_id"])
    op.create_index("ix_journal_entries_org_id", "journal_entries", ["org_id"])
    op.create_index("ix_journal_entries_date", "journal_entries", ["date"])
    op.create_index("ix_journal_entries_tenant_date", "journal_entries", ["user_id", "date"])

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["chart_accounts.id"]),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])

    op.create_table(
        "vendor_bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("bill_number", sa.String(length=50), nullable=False),
        sa.Column("vendor_contact_id", sa.Uuid(), nullable=True),
        sa.Column("vendor_name", sa.String(length=255), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", _BILL_STATUS, nullable=False),
        sa.Column("approval_journal_id", sa.Uuid(), nullable=True),
        sa.Column("payment_journal_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_payment_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("user_id", "org_id", "bill_number", name="uq_vendor_bill_tenant_number"),
    )
    op.create_index("ix_vendor_bills_user_id", "vendor_bills", ["user_id"])
    op.create_index("ix_vendor_bills_org_id", "vendor_bills", ["org_id"])
    op.create_index("ix_vendor_bills_bill_date", "vendor_bills", ["bill_date"])

    op.create_table(
        "vendor_bill_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["bill_id"], ["vendor_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["chart_accounts.id"]),
    )
    op.create_index("ix_vendor_bill_lines_bill_id", "vendor_bill_lines", ["bill_id"])

    # CoA mapping columns on the existing category / payment-account tables.
    op.add_column("transaction_categories", sa.Column("coa_account_id", sa.Uuid(), nullable=True))
    op.add_column("payment_accounts", sa.Column("coa_account_id", sa.Uuid(), nullable=True))
    # 1099 flag on contacts.
    op.add_column("contacts", sa.Column("is_1099_vendor", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("contacts", "is_1099_vendor")
    op.drop_column("payment_accounts", "coa_account_id")
    op.drop_column("transaction_categories", "coa_account_id")
    op.drop_index("ix_vendor_bill_lines_bill_id", table_name="vendor_bill_lines")
    op.drop_table("vendor_bill_lines")
    for ix in ("ix_vendor_bills_bill_date", "ix_vendor_bills_org_id", "ix_vendor_bills_user_id"):
        op.drop_index(ix, table_name="vendor_bills")
    op.drop_table("vendor_bills")
    for ix in ("ix_journal_lines_account_id", "ix_journal_lines_journal_entry_id"):
        op.drop_index(ix, table_name="journal_lines")
    op.drop_table("journal_lines")
    for ix in ("ix_journal_entries_tenant_date", "ix_journal_entries_date", "ix_journal_entries_org_id", "ix_journal_entries_user_id"):
        op.drop_index(ix, table_name="journal_entries")
    op.drop_table("journal_entries")
    for ix in ("ix_chart_accounts_tenant_type", "ix_chart_accounts_code", "ix_chart_accounts_org_id", "ix_chart_accounts_user_id"):
        op.drop_index(ix, table_name="chart_accounts")
    op.drop_table("chart_accounts")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _BILL_STATUS.drop(bind, checkfirst=True)
        _JE_STATUS.drop(bind, checkfirst=True)
        _ACCT_TYPE.drop(bind, checkfirst=True)
