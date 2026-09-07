"""Joint filing: T1 line on personal categories.

Additive. Lets the personal ledger carry the six tax-relevant categories
(RRSP, medical, donations, childcare, tuition, union dues) that flow to a T1,
without touching the business tables. The joint filing package reads both
ledgers; it never writes into personal.

Revision ID: k9h0a1b2c3d4
Revises: j8g9h0a1b2c3
"""
import sqlalchemy as sa
from alembic import op

revision = "k9h0a1b2c3d4"
down_revision = "j8g9h0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personal_categories", sa.Column("t1_line", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("personal_categories", "t1_line")
