"""GST/HST return summary — the CRA GST34 lines, computed from the cashbook.

Unlike tax_service.get_tax_liability_report (which reads the legacy Invoice +
Expense tables, disconnected from the cashbook), this reads the canonical
CashbookEntry tax columns so it ties to the same books the Bank Scanner posts to
and the P&L reads. Single source of truth.

Province-aware since the Canadian tax matrix (alembic i7f8a9b0c1d2):

  - Only the CRA-remitted portion of tax lands on the GST34. That is
    ``tax_gst_hst_amount`` where recorded; on pre-matrix rows it is NULL and
    ``tax_amount`` is treated as all-CRA (the old Ontario-HST assumption), via
    COALESCE(tax_gst_hst_amount, tax_amount).
  - PST / RST / QST (``tax_pst_amount``) is remitted to the province and is
    reported in a separate block so the accountant sees it, but never on the
    GST34 lines.

The lines mirror a Canadian GST/HST return:
  - Line 101  Sales & other revenue (net of tax)   = Σ (income total − income tax)
  - Line 105  GST/HST collected                      = Σ CRA tax on INCOME entries
  - Line 108  Input tax credits (ITCs)               = Σ CRA tax on EXPENSE entries
  - Line 109  Net tax  (owe if +, refund if −)       = 105 − 108

It reports only tax that has actually been RECORDED on entries. If none has been
(tax_amount NULL/0), every line is zero and `has_recorded_tax` is False — that's
factual, not an estimate. It is a summary to hand an accountant, not a filing.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.cashbook.models import CashbookEntry, CategoryType, EntryType, TransactionCategory
from app.core.authorization import apply_cashbook_filter

_ZERO = Decimal("0.00")


def _q(v) -> Decimal:
    return (v if isinstance(v, Decimal) else Decimal(str(v or 0))).quantize(Decimal("0.01"))


async def gst_hst_return(
    db: AsyncSession,
    user: User,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Aggregate recorded tax off the cashbook into GST34-style return lines."""
    # CRA portion: the split column where recorded, else the whole tax (legacy rows).
    cra_tax = func.coalesce(
        func.sum(func.coalesce(CashbookEntry.tax_gst_hst_amount, CashbookEntry.tax_amount)), 0
    )
    # Province portion: only the split column — legacy rows have none.
    prov_tax = func.coalesce(func.sum(CashbookEntry.tax_pst_amount), 0)
    total_tax = func.coalesce(func.sum(CashbookEntry.tax_amount), 0)
    gross = func.coalesce(func.sum(CashbookEntry.total_amount), 0)
    taxed = func.count(CashbookEntry.id).filter(CashbookEntry.tax_amount > 0)

    # Owner's Draw / Contribution (equity) are personal money through a business
    # account — never part of a GST/HST return. Exclude them (keep uncategorized).
    equity_ids = select(TransactionCategory.id).where(
        TransactionCategory.category_type == CategoryType.EQUITY
    )

    stmt = select(
        CashbookEntry.entry_type,
        cra_tax.label("cra"),
        prov_tax.label("prov"),
        total_tax.label("tax"),
        gross.label("gross"),
        taxed.label("taxed"),
    ).where(
        or_(CashbookEntry.category_id.is_(None), CashbookEntry.category_id.notin_(equity_ids))
    ).group_by(CashbookEntry.entry_type)
    if date_from:
        stmt = stmt.where(CashbookEntry.date >= date_from)
    if date_to:
        stmt = stmt.where(CashbookEntry.date <= date_to)
    stmt = apply_cashbook_filter(stmt, CashbookEntry.user_id, CashbookEntry.org_id, user)

    income_cra = income_prov = income_tax = income_gross = _ZERO
    expense_cra = expense_prov = _ZERO
    taxed_count = 0
    for entry_type, cra, prov, t, g, n in (await db.execute(stmt)).all():
        if entry_type == EntryType.INCOME:
            income_cra, income_prov, income_tax, income_gross = _q(cra), _q(prov), _q(t), _q(g)
        elif entry_type == EntryType.EXPENSE:
            expense_cra, expense_prov = _q(cra), _q(prov)
        taxed_count += int(n or 0)

    line_101 = _q(income_gross - income_tax)   # revenue net of ALL collected tax
    line_105 = income_cra                      # GST/HST collected (CRA portion only)
    line_108 = expense_cra                     # input tax credits (CRA portion only)
    line_109 = _q(line_105 - line_108)         # net tax

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": (date_to or date.today()).isoformat(),
        "line_101_sales": line_101,
        "line_105_collected": line_105,
        "line_108_itc": line_108,
        "line_109_net_tax": line_109,
        "owes_cra": line_109 > _ZERO,
        "has_recorded_tax": taxed_count > 0,
        "taxed_entry_count": taxed_count,
        # Provincial sales tax — remitted to the province (BC/SK/MB PST, QC QST),
        # NOT on the GST34. Zero for HST / GST-only provinces.
        "provincial": {
            "collected": income_prov,
            "paid": expense_prov,
            "net": _q(income_prov - expense_prov),
        },
    }
