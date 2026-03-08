"""add meeting_type tokens to calendar_bookings

Revision ID: 46776971ed90
Revises: fe4e69e28d5b
Create Date: 2026-03-07 21:44:03.964012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46776971ed90'
down_revision: Union[str, None] = 'fe4e69e28d5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('calendar_bookings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meeting_type', sa.Enum('PHONE', 'VIDEO', 'IN_PERSON', name='meetingtype'), nullable=True))
        batch_op.add_column(sa.Column('meeting_location', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('reschedule_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('cancel_token', sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint('uq_booking_reschedule_token', ['reschedule_token'])
        batch_op.create_unique_constraint('uq_booking_cancel_token', ['cancel_token'])


def downgrade() -> None:
    with op.batch_alter_table('calendar_bookings', schema=None) as batch_op:
        batch_op.drop_constraint('uq_booking_cancel_token', type_='unique')
        batch_op.drop_constraint('uq_booking_reschedule_token', type_='unique')
        batch_op.drop_column('cancel_token')
        batch_op.drop_column('reschedule_token')
        batch_op.drop_column('meeting_location')
        batch_op.drop_column('meeting_type')
