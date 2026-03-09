"""Add currency to payment_accounts, make cashbook entry account_id nullable

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-08
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add currency column to payment_accounts
    with op.batch_alter_table("payment_accounts") as batch_op:
        batch_op.add_column(sa.Column("currency", sa.String(3), nullable=False, server_default="CAD"))

    # Make account_id nullable and change ondelete to SET NULL
    with op.batch_alter_table("cashbook_entries") as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("cashbook_entries") as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Uuid(), nullable=False)

    with op.batch_alter_table("payment_accounts") as batch_op:
        batch_op.drop_column("currency")
