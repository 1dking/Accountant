"""Business/Personal mode: users.active_mode + the encrypted personal ledger.

Additive only — no existing business table is altered. Adds one column to users
(defaulting 'business' so every current user is unchanged) and creates the three
personal-ledger tables. Encrypted columns (name, amount, description, notes,
opening_balance) are Text at the DB level; the app layers Fernet on top via
EncryptedString/EncryptedNumeric.

Revision ID: g5d6e7f8a9b0
Revises: f4c5d6e7a8b9
"""
import sqlalchemy as sa
from alembic import op

revision = "g5d6e7f8a9b0"
down_revision = "f4c5d6e7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("active_mode", sa.String(20), server_default="business", nullable=False),
    )

    op.create_table(
        "personal_accounts",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("user_id", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),  # encrypted
        sa.Column("account_type", sa.String(30), nullable=False, server_default="bank"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CAD"),
        sa.Column("opening_balance", sa.Text(), nullable=False),  # encrypted
        sa.Column("opening_balance_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_personal_accounts_user_id", "personal_accounts", ["user_id"])

    op.create_table(
        "personal_categories",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("user_id", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False, server_default="both"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_personal_categories_user_id", "personal_categories", ["user_id"])

    op.create_table(
        "personal_transactions",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("user_id", sa.CHAR(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.CHAR(32), sa.ForeignKey("personal_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("amount", sa.Text(), nullable=False),  # encrypted
        sa.Column("description", sa.Text(), nullable=False),  # encrypted
        sa.Column("category_id", sa.CHAR(32), sa.ForeignKey("personal_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),  # encrypted
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_personal_transactions_user_id", "personal_transactions", ["user_id"])
    op.create_index("ix_personal_transactions_account_id", "personal_transactions", ["account_id"])
    op.create_index("ix_personal_transactions_date", "personal_transactions", ["date"])
    op.create_index("ix_personal_transactions_source_id", "personal_transactions", ["source_id"])


def downgrade() -> None:
    op.drop_table("personal_transactions")
    op.drop_table("personal_categories")
    op.drop_table("personal_accounts")
    op.drop_column("users", "active_mode")
