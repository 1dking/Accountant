"""add_tax_rates_table

Revision ID: 52bb923d86c1
Revises: e12173543a22
Create Date: 2026-02-27 03:13:09.705355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52bb923d86c1'
down_revision: Union[str, None] = 'e12173543a22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tax_rates',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('rate', sa.Float(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('region', sa.String(length=100), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('tax_rates')
