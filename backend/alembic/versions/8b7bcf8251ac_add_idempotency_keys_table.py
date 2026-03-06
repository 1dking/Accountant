"""Add idempotency_keys table

Revision ID: 8b7bcf8251ac
Revises: c359fd368cae
Create Date: 2026-03-05 12:37:14.515520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b7bcf8251ac'
down_revision: Union[str, None] = 'c359fd368cae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('idempotency_keys', schema=None) as batch_op:
        batch_op.create_index('ix_idempotency_keys_key', ['key'], unique=False)
        batch_op.create_index('ix_idempotency_keys_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('idempotency_keys', schema=None) as batch_op:
        batch_op.drop_index('ix_idempotency_keys_user_id')
        batch_op.drop_index('ix_idempotency_keys_key')
    op.drop_table('idempotency_keys')
