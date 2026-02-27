"""add integration_configs table

Revision ID: e12173543a22
Revises: a7bac2d41f69
Create Date: 2026-02-27 00:47:44.813621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e12173543a22'
down_revision: Union[str, None] = 'a7bac2d41f69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('integration_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('integration_type', sa.String(length=50), nullable=False),
        sa.Column('encrypted_config', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_integration_configs_integration_type'), 'integration_configs', ['integration_type'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_integration_configs_integration_type'), table_name='integration_configs')
    op.drop_table('integration_configs')
