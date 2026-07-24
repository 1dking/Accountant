"""Add refunded_amount / refunded_at to proposals (admin Stripe refunds)

Revision ID: w9x0y1z2a3b4
Revises: q3r4s5t6u7v8
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w9x0y1z2a3b4"
down_revision: Union[str, None] = "q3r4s5t6u7v8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("refunded_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("proposals", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("proposals", "refunded_at")
    op.drop_column("proposals", "refunded_amount")
