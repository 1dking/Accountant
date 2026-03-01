"""make payment_url nullable for embedded payments

Revision ID: a1b2c3d4e5f6
Revises: ef290c80372d
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "ef290c80372d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stripe_payment_links") as batch_op:
        batch_op.alter_column("payment_url", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("stripe_payment_links") as batch_op:
        batch_op.alter_column("payment_url", existing_type=sa.Text(), nullable=False)
