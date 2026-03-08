"""Add dnd_enabled, lead_source, job_title, custom_fields_data to contacts

Revision ID: fe4e69e28d5b
Revises: ab286478fc11
Create Date: 2026-03-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe4e69e28d5b'
down_revision: Union[str, None] = 'ab286478fc11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('contacts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dnd_enabled', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('lead_source', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('job_title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('custom_fields_data', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('contacts', schema=None) as batch_op:
        batch_op.drop_column('custom_fields_data')
        batch_op.drop_column('job_title')
        batch_op.drop_column('lead_source')
        batch_op.drop_column('dnd_enabled')
