"""add company settings, public access tokens, and estimate signatures

Revision ID: d4a1b9e3c567
Revises: cfbf3dcffee1
Create Date: 2026-02-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4a1b9e3c567'
down_revision: Union[str, None] = 'cfbf3dcffee1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Company Settings table --
    op.create_table(
        'company_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('company_email', sa.String(length=255), nullable=True),
        sa.Column('company_phone', sa.String(length=50), nullable=True),
        sa.Column('company_website', sa.String(length=255), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=True),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('zip_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('logo_storage_path', sa.String(length=500), nullable=True),
        sa.Column('default_tax_rate_id', sa.String(length=36), nullable=True),
        sa.Column('default_currency', sa.String(length=3), server_default='CAD', nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['default_tax_rate_id'], ['tax_rates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # -- Public Access Tokens table --
    op.create_table(
        'public_access_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.Enum('estimate', 'invoice', name='resourcetype'), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('view_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('public_access_tokens') as batch_op:
        batch_op.create_index('ix_public_access_tokens_token', ['token'], unique=True)

    # -- Add e-signature fields to estimates table --
    with op.batch_alter_table('estimates') as batch_op:
        batch_op.add_column(sa.Column('signature_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('signed_by_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('signer_ip', sa.String(length=45), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('estimates') as batch_op:
        batch_op.drop_column('signer_ip')
        batch_op.drop_column('signed_at')
        batch_op.drop_column('signed_by_name')
        batch_op.drop_column('signature_data')

    op.drop_table('public_access_tokens')
    op.drop_table('company_settings')
