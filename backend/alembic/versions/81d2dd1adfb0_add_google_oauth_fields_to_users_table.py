"""Add Google OAuth fields to users table

Revision ID: 81d2dd1adfb0
Revises: 8b7bcf8251ac
Create Date: 2026-03-05 20:34:46.569526

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81d2dd1adfb0'
down_revision: Union[str, None] = '8b7bcf8251ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_provider', sa.String(length=20), server_default='local', nullable=False))
        batch_op.add_column(sa.Column('google_id', sa.String(length=255), nullable=True))
        batch_op.alter_column('hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.create_unique_constraint('uq_users_google_id', ['google_id'])


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_google_id', type_='unique')
        batch_op.alter_column('hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.drop_column('google_id')
        batch_op.drop_column('auth_provider')
