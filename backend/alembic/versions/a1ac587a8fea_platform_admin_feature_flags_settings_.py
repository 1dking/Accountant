"""platform_admin_feature_flags_settings_errors

Revision ID: a1ac587a8fea
Revises: e1e481069afe
Create Date: 2026-03-08 17:01:50.611113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1ac587a8fea'
down_revision: Union[str, None] = 'e1e481069afe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Feature flags table
    op.create_table(
        'feature_flags',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('category', sa.String(length=50), server_default='general', nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('feature_flags', schema=None) as batch_op:
        batch_op.create_index('ix_feature_flags_key', ['key'], unique=True)

    # Platform settings table
    op.create_table(
        'platform_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), server_default='general', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(length=20), server_default='string', nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('platform_settings', schema=None) as batch_op:
        batch_op.create_index('ix_platform_settings_key', ['key'], unique=True)

    # Error logs table
    op.create_table(
        'error_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('level', sa.String(length=20), server_default='error', nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('traceback', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('request_path', sa.String(length=500), nullable=True),
        sa.Column('request_method', sa.String(length=10), nullable=True),
        sa.Column('resolved', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('resolved_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('error_logs')
    with op.batch_alter_table('platform_settings', schema=None) as batch_op:
        batch_op.drop_index('ix_platform_settings_key')
    op.drop_table('platform_settings')
    with op.batch_alter_table('feature_flags', schema=None) as batch_op:
        batch_op.drop_index('ix_feature_flags_key')
    op.drop_table('feature_flags')
