"""Convert monetary Float columns to Numeric for Decimal precision

Revision ID: c359fd368cae
Revises: 21e75ba17338
Create Date: 2026-03-05 12:27:53.975836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c359fd368cae'
down_revision: Union[str, None] = '21e75ba17338'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('cashbook_entries', schema=None) as batch_op:
        batch_op.alter_column('total_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
        batch_op.alter_column('tax_rate_used',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=5, scale=2),
               existing_nullable=True)

    with op.batch_alter_table('estimate_line_items', schema=None) as batch_op:
        batch_op.alter_column('quantity',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=10, scale=4),
               existing_nullable=False)
        batch_op.alter_column('unit_price',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=5, scale=2),
               existing_nullable=True)
        batch_op.alter_column('total',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('estimates', schema=None) as batch_op:
        batch_op.alter_column('subtotal',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=5, scale=2),
               existing_nullable=True)
        batch_op.alter_column('tax_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
        batch_op.alter_column('discount_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('total',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('expense_line_items', schema=None) as batch_op:
        batch_op.alter_column('quantity',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=10, scale=4),
               existing_nullable=True)
        batch_op.alter_column('unit_price',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
        batch_op.alter_column('total',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)

    with op.batch_alter_table('income_entries', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('invoice_line_items', schema=None) as batch_op:
        batch_op.alter_column('quantity',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=10, scale=4),
               existing_nullable=False)
        batch_op.alter_column('unit_price',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=5, scale=2),
               existing_nullable=True)
        batch_op.alter_column('total',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('invoice_payments', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.alter_column('subtotal',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=5, scale=2),
               existing_nullable=True)
        batch_op.alter_column('tax_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
        batch_op.alter_column('discount_amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
        batch_op.alter_column('total',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.alter_column('opening_balance',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('plaid_transactions', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('stripe_payment_links', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)

    with op.batch_alter_table('stripe_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('stripe_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('stripe_payment_links', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('plaid_transactions', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.alter_column('opening_balance',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.alter_column('total',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('discount_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('tax_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('tax_rate',
               existing_type=sa.Numeric(precision=5, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('subtotal',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('invoice_payments', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('invoice_line_items', schema=None) as batch_op:
        batch_op.alter_column('total',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.Numeric(precision=5, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('unit_price',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('quantity',
               existing_type=sa.Numeric(precision=10, scale=4),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('income_entries', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('tax_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('expense_line_items', schema=None) as batch_op:
        batch_op.alter_column('total',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('unit_price',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('quantity',
               existing_type=sa.Numeric(precision=10, scale=4),
               type_=sa.FLOAT(),
               existing_nullable=True)

    with op.batch_alter_table('estimates', schema=None) as batch_op:
        batch_op.alter_column('total',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('discount_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('tax_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('tax_rate',
               existing_type=sa.Numeric(precision=5, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('subtotal',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('estimate_line_items', schema=None) as batch_op:
        batch_op.alter_column('total',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('tax_rate',
               existing_type=sa.Numeric(precision=5, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('unit_price',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
        batch_op.alter_column('quantity',
               existing_type=sa.Numeric(precision=10, scale=4),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('cashbook_entries', schema=None) as batch_op:
        batch_op.alter_column('tax_rate_used',
               existing_type=sa.Numeric(precision=5, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('tax_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('total_amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)

    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
