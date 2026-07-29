"""GST/HST return summary — the CRA GST34 lines, computed from the cashbook.

Unlike tax_service.get_tax_liability_report (which reads the legacy Invoice +
Expense tables, disconnected from the cashbook), this reads the canonical
CashbookEntry.tax_amount so it ties to the same books the Bank Scanner posts to
and the P&L reads. Single source of truth.

The lines mirror a Canadian GST/HST return:
  - Line 101  Sales & other revenue (net of tax)   = Σ (income total − income tax)
  - Line 105  GST/HST collected                      = Σ tax on INCOME entries
  - Line 108  Input tax credits (ITCs)               = Σ tax on EXPENSE entries
  - Line 109  Net tax  (owe if +, refund if −)       = 105 − 108

It reports only tax that has actually been RECORDED on entries. If none has been
(tax_amount NULL/0), every line is zero and `has_recorded_tax` is False — that's
factual, not an estimate. It is a summary to hand an accountant, not a filing.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.cashbook.models import CashbookEntry, EntryType
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
    tax = func.coalesce(func.sum(CashbookEntry.tax_amount), 0)
    gross = func.coalesce(func.sum(CashbookEntry.total_amount), 0)
    taxed = func.count(CashbookEntry.id).filter(CashbookEntry.tax_amount > 0)

    stmt = select(
        CashbookEntry.entry_type, tax.label("tax"), gross.label("gross"), taxed.label("taxed"),
    ).group_by(CashbookEntry.entry_type)
    if date_from:
        stmt = stmt.where(CashbookEntry.date >= date_from)
    if date_to:
        stmt = stmt.where(CashbookEntry.date <= date_to)
    stmt = apply_cashbook_filter(stmt, CashbookEntry.user_id, CashbookEntry.org_id, user)

    income_tax = income_gross = expense_tax = _ZERO
    taxed_count = 0
    for entry_type, t, g, n in (await db.execute(stmt)).all():
        if entry_type == EntryType.INCOME:
            income_tax = _q(t)
            income_gross = _q(g)
        elif entry_type == EntryType.EXPENSE:
            expense_tax = _q(t)
        taxed_count += int(n or 0)

    line_101 = _q(income_gross - income_tax)   # revenue net of collected tax
    line_105 = income_tax                      # GST/HST collected
    line_108 = expense_tax                     # input tax credits
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
    }
