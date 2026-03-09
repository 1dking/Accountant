"""Cashbook status, soft delete, split transactions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cashbook_entries") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(20), nullable=False, server_default="pending")
        )
        batch_op.add_column(
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "split_parent_id",
                sa.Uuid(),
                sa.ForeignKey("cashbook_entries.id", ondelete="CASCADE"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("cashbook_entries") as batch_op:
        batch_op.drop_column("split_parent_id")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("status")
