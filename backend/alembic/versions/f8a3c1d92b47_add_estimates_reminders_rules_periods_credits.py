"""add estimates, reminders, categorization rules, periods, credit notes

Revision ID: f8a3c1d92b47
Revises: 52bb923d86c1
Create Date: 2026-02-27 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a3c1d92b47'
down_revision: Union[str, None] = '52bb923d86c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Estimates ---
    op.create_table('estimates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('estimate_number', sa.String(length=20), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'CONVERTED', name='estimatestatus'), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('tax_rate', sa.Float(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('converted_invoice_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['converted_invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('estimate_number'),
    )
    with op.batch_alter_table('estimates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_estimates_contact_id'), ['contact_id'], unique=False)

    op.create_table('estimate_line_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('estimate_id', sa.Uuid(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('tax_rate', sa.Float(), nullable=True),
        sa.Column('total', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['estimate_id'], ['estimates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('estimate_line_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_estimate_line_items_estimate_id'), ['estimate_id'], unique=False)

    # --- Reminder Rules ---
    op.create_table('reminder_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('days_offset', sa.Integer(), nullable=False, comment='Negative = before due, 0 = on due date, positive = after due'),
        sa.Column('channel', sa.Enum('EMAIL', 'SMS', 'BOTH', name='reminderchannel'), nullable=False),
        sa.Column('email_subject', sa.String(length=500), nullable=True),
        sa.Column('email_body', sa.Text(), nullable=True),
        sa.Column('sms_body', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- Payment Reminders ---
    op.create_table('payment_reminders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=False),
        sa.Column('reminder_rule_id', sa.Uuid(), nullable=True),
        sa.Column('reminder_type', sa.String(length=50), nullable=False, comment="e.g. 'before_due', 'on_due', 'after_due', 'manual'"),
        sa.Column('channel', sa.Enum('EMAIL', 'SMS', 'BOTH', name='reminderchannel', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('SENT', 'FAILED', 'SKIPPED', name='reminderstatus'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reminder_rule_id'], ['reminder_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('payment_reminders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_reminders_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_reminders_contact_id'), ['contact_id'], unique=False)

    # --- Categorization Rules ---
    op.create_table('categorization_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('match_field', sa.Enum('NAME', 'MERCHANT_NAME', 'CATEGORY', name='matchfield'), nullable=False),
        sa.Column('match_type', sa.Enum('CONTAINS', 'EXACT', 'STARTS_WITH', 'REGEX', name='matchtype'), nullable=False),
        sa.Column('match_value', sa.String(length=500), nullable=False),
        sa.Column('assign_category_id', sa.Uuid(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['assign_category_id'], ['expense_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- Accounting Periods ---
    op.create_table('accounting_periods',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', name='periodstatus'), nullable=False),
        sa.Column('closed_by', sa.Uuid(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['closed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('accounting_periods', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_accounting_periods_year'), ['year'], unique=False)
        batch_op.create_index(batch_op.f('ix_accounting_periods_month'), ['month'], unique=False)

    # --- Credit Notes ---
    op.create_table('credit_notes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('credit_note_number', sa.String(length=20), nullable=False),
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'ISSUED', 'APPLIED', name='creditnotestatus'), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credit_note_number'),
    )
    with op.batch_alter_table('credit_notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_credit_notes_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_credit_notes_contact_id'), ['contact_id'], unique=False)


def downgrade() -> None:
    op.drop_table('credit_notes')
    op.drop_table('accounting_periods')
    op.drop_table('categorization_rules')
    op.drop_table('payment_reminders')
    op.drop_table('reminder_rules')
    op.drop_table('estimate_line_items')
    op.drop_table('estimates')
