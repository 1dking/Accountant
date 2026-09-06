"""Canadian tax matrix: province on company, structured tax rates, split tax components.

Additive only. Nothing existing changes meaning:

- ``tax_amount`` on every line/entry stays the TOTAL tax, so every existing
  report keeps summing the same column.
- New ``tax_gst_hst_amount`` is the CRA-remitted portion (GST, or the whole
  HST); new ``tax_pst_amount`` is the province-remitted portion (PST/RST/QST).
  NULL on pre-matrix rows means "all of tax_amount was CRA" — the pre-matrix
  Ontario-HST assumption — and readers use COALESCE(tax_gst_hst_amount, tax_amount).
- ``tax_rates`` gains a jurisdiction shape (tax_type, province, is_recoverable)
  so a BC PST row is distinguishable from an Ontario HST row. Existing rows
  keep working: the new columns are nullable and ``region`` is untouched.
- ``company_settings`` gains the province that drives default rates, plus the
  CRA identifiers T2125/T2/GST34 print.

Revision ID: i7f8a9b0c1d2
Revises: h6e7f8a9b0c1
"""
import sqlalchemy as sa
from alembic import op

revision = "i7f8a9b0c1d2"
down_revision = "h6e7f8a9b0c1"
branch_labels = None
depends_on = None


_TAX_SPLIT_TABLES = ("cashbook_entries", "invoices", "expenses")


def upgrade() -> None:
    # ── company_settings: where is this business, and who is it to the CRA ──
    op.add_column("company_settings", sa.Column("province", sa.String(2), nullable=True))
    op.add_column("company_settings", sa.Column("business_number", sa.String(15), nullable=True))
    op.add_column("company_settings", sa.Column("gst_hst_number", sa.String(15), nullable=True))
    op.add_column("company_settings", sa.Column("fiscal_year_end_month", sa.Integer(), nullable=True))

    # ── tax_rates: jurisdiction shape ──
    op.add_column("tax_rates", sa.Column("tax_type", sa.String(10), nullable=True))   # gst|hst|pst|rst|qst|other
    op.add_column("tax_rates", sa.Column("province", sa.String(2), nullable=True))     # NULL = federal
    op.add_column(
        "tax_rates",
        sa.Column("is_recoverable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tax_rates",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("tax_rates", sa.Column("effective_from", sa.Date(), nullable=True))
    op.create_index("ix_tax_rates_type_province", "tax_rates", ["tax_type", "province"])

    # ── split tax components on every amount-bearing table ──
    for table in _TAX_SPLIT_TABLES:
        op.add_column(table, sa.Column("tax_gst_hst_amount", sa.Numeric(12, 2), nullable=True))
        op.add_column(table, sa.Column("tax_pst_amount", sa.Numeric(12, 2), nullable=True))
        op.add_column(
            table,
            sa.Column("tax_rate_id", sa.String(36),
                      sa.ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("tax_rate_2_id", sa.String(36),
                      sa.ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True),
        )

    # Line items carry rates, not amounts (header carries amounts) — so they get
    # the rate FKs plus a second rate percentage for the PST leg.
    op.add_column("invoice_line_items", sa.Column("tax_rate_2", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "invoice_line_items",
        sa.Column("tax_rate_id", sa.String(36),
                  sa.ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "invoice_line_items",
        sa.Column("tax_rate_2_id", sa.String(36),
                  sa.ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    for col in ("tax_rate_2_id", "tax_rate_id", "tax_rate_2"):
        op.drop_column("invoice_line_items", col)
    for table in _TAX_SPLIT_TABLES:
        for col in ("tax_rate_2_id", "tax_rate_id", "tax_pst_amount", "tax_gst_hst_amount"):
            op.drop_column(table, col)
    op.drop_index("ix_tax_rates_type_province", "tax_rates")
    for col in ("effective_from", "is_system", "is_recoverable", "province", "tax_type"):
        op.drop_column("tax_rates", col)
    for col in ("fiscal_year_end_month", "gst_hst_number", "business_number", "province"):
        op.drop_column("company_settings", col)
