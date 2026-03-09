"""Add cashbook_access to users, org_id to payment_accounts and cashbook_entries

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cashbook_access to users (default 'personal')
    op.add_column(
        "users",
        sa.Column("cashbook_access", sa.String(20), server_default="personal", nullable=False),
    )

    # Add org_id to payment_accounts
    op.add_column(
        "payment_accounts",
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_accounts_org_id",
        "payment_accounts",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_payment_accounts_org_id", "payment_accounts", ["org_id"])

    # Add org_id to cashbook_entries
    op.add_column(
        "cashbook_entries",
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cashbook_entries_org_id",
        "cashbook_entries",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_cashbook_entries_org_id", "cashbook_entries", ["org_id"])

    # Backfill: set org_id on existing records based on owner's org_id
    op.execute("""
        UPDATE payment_accounts
        SET org_id = u.org_id
        FROM users u
        WHERE payment_accounts.user_id = u.id
          AND u.org_id IS NOT NULL
    """)
    op.execute("""
        UPDATE cashbook_entries
        SET org_id = u.org_id
        FROM users u
        WHERE cashbook_entries.user_id = u.id
          AND u.org_id IS NOT NULL
    """)

    # Set admin users to 'org' cashbook access by default
    op.execute("""
        UPDATE users SET cashbook_access = 'org'
        WHERE role = 'ADMIN'
          AND org_id IS NOT NULL
    """)
    # Set accountant users to 'org' cashbook access by default
    op.execute("""
        UPDATE users SET cashbook_access = 'org'
        WHERE role = 'ACCOUNTANT'
          AND org_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_cashbook_entries_org_id", table_name="cashbook_entries")
    op.drop_constraint("fk_cashbook_entries_org_id", "cashbook_entries", type_="foreignkey")
    op.drop_column("cashbook_entries", "org_id")

    op.drop_index("ix_payment_accounts_org_id", table_name="payment_accounts")
    op.drop_constraint("fk_payment_accounts_org_id", "payment_accounts", type_="foreignkey")
    op.drop_column("payment_accounts", "org_id")

    op.drop_column("users", "cashbook_access")
