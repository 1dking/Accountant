"""add cashbook tables

Revision ID: 6eb875a50e5d
Revises: f8a3c1d92b47
Create Date: 2026-02-27 20:16:14.014173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6eb875a50e5d'
down_revision: Union[str, None] = 'f8a3c1d92b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Transaction categories (unified income + expense categories)
    op.create_table('transaction_categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('category_type', sa.Enum('INCOME', 'EXPENSE', 'BOTH', name='categorytype'), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('icon', sa.String(length=50), nullable=True),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    # Payment accounts (bank accounts, credit cards)
    op.create_table('payment_accounts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('account_type', sa.Enum('BANK', 'CREDIT_CARD', name='accounttype'), nullable=False),
    sa.Column('opening_balance', sa.Float(), nullable=False),
    sa.Column('opening_balance_date', sa.Date(), nullable=False),
    sa.Column('default_tax_rate_id', sa.String(length=36), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['default_tax_rate_id'], ['tax_rates.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_accounts_user_id'), ['user_id'], unique=False)

    # Cashbook entries (unified transaction ledger)
    op.create_table('cashbook_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('account_id', sa.Uuid(), nullable=False),
    sa.Column('entry_type', sa.Enum('INCOME', 'EXPENSE', name='entrytype'), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('total_amount', sa.Float(), nullable=False),
    sa.Column('tax_amount', sa.Float(), nullable=True),
    sa.Column('tax_rate_used', sa.Float(), nullable=True),
    sa.Column('tax_override', sa.Boolean(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=True),
    sa.Column('contact_id', sa.Uuid(), nullable=True),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=True),
    sa.Column('source_id', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['payment_accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['category_id'], ['transaction_categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cashbook_entries', schema=None) as batch_op:
        batch_op.create_index('ix_cashbook_entries_account_date', ['account_id', 'date'], unique=False)
        batch_op.create_index(batch_op.f('ix_cashbook_entries_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cashbook_entries_category_id'), ['category_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cashbook_entries_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_cashbook_entries_entry_type'), ['entry_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_cashbook_entries_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('cashbook_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cashbook_entries_user_id'))
        batch_op.drop_index(batch_op.f('ix_cashbook_entries_entry_type'))
        batch_op.drop_index(batch_op.f('ix_cashbook_entries_date'))
        batch_op.drop_index(batch_op.f('ix_cashbook_entries_category_id'))
        batch_op.drop_index(batch_op.f('ix_cashbook_entries_account_id'))
        batch_op.drop_index('ix_cashbook_entries_account_date')

    op.drop_table('cashbook_entries')

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_accounts_user_id'))

    op.drop_table('payment_accounts')
    op.drop_table('transaction_categories')
