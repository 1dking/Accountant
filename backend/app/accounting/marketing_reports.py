"""Marketing performance — blended ROAS from the same postings as the statements.

For an agency, the CFO-level question is "for every dollar of ad spend, how much
revenue did the business bring in?" This computes that *blended* (business-wide,
not campaign-attributed) from the cashbook, so it ties to the P&L:

  - Revenue  = all INCOME postings (credit − debit).
  - Ad spend = EXPENSE postings whose resolved account looks like advertising
               (name contains "advertis" or "marketing").
  - Blended ROAS = revenue / ad spend.

Trended by month, plus totals and the advertising accounts that make up the
spend. It is deliberately *blended*: it does not attribute revenue to specific
campaigns (the cashbook has no click/conversion data). That's the honest limit —
it answers efficiency, not attribution.
"""
from collections import OrderedDict
from decimal import Decimal

from app.accounting.ledger_models import AccountType
from app.accounting.ledger_reports import Posting

_ZERO = Decimal("0")
_AD_KEYWORDS = ("advertis", "marketing")


def _is_ad_account(name: str) -> bool:
    low = (name or "").lower()
    return any(k in low for k in _AD_KEYWORDS)


def _roas(revenue: Decimal, ad_spend: Decimal) -> Decimal | None:
    """Revenue per dollar of ad spend, rounded to 2dp. None when no spend."""
    if ad_spend <= _ZERO:
        return None
    return (revenue / ad_spend).quantize(Decimal("0.01"))


def marketing_performance(postings: list[Posting]) -> dict:
    """Monthly revenue vs ad spend + blended ROAS. Feed it the same postings as
    profit_loss (no opening balances needed)."""
    months: "OrderedDict[str, dict]" = OrderedDict()
    ad_accounts: dict[str, dict] = {}
    total_revenue = total_ad_spend = _ZERO

    for p in postings:
        if p.account_type not in (AccountType.INCOME, AccountType.EXPENSE):
            continue
        key = f"{p.date.year:04d}-{p.date.month:02d}"
        m = months.setdefault(key, {"month": key, "revenue": _ZERO, "ad_spend": _ZERO})
        if p.account_type == AccountType.INCOME:
            amt = p.credit - p.debit
            m["revenue"] += amt
            total_revenue += amt
        elif _is_ad_account(p.name):
            amt = p.debit - p.credit
            m["ad_spend"] += amt
            total_ad_spend += amt
            row = ad_accounts.setdefault(p.account_key, {"code": p.code, "name": p.name, "amount": _ZERO})
            row["amount"] += amt

    month_rows = []
    for m in sorted(months.values(), key=lambda r: r["month"]):
        month_rows.append({
            "month": m["month"],
            "revenue": m["revenue"],
            "ad_spend": m["ad_spend"],
            "net": m["revenue"] - m["ad_spend"],
            "roas": _roas(m["revenue"], m["ad_spend"]),
        })

    ad_breakdown = sorted(
        (r for r in ad_accounts.values() if r["amount"] != _ZERO),
        key=lambda r: r["amount"], reverse=True,
    )

    return {
        "months": month_rows,
        "ad_spend_by_account": ad_breakdown,
        "total_revenue": total_revenue,
        "total_ad_spend": total_ad_spend,
        "blended_roas": _roas(total_revenue, total_ad_spend),
        "net_after_ad_spend": total_revenue - total_ad_spend,
    }
