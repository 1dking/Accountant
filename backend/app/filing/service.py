"""Joint filing package — T2125 from the books, T1 summary from the personal
ledger, one readiness checklist. Read-only everywhere.

Business side reads the exact postings the P&L reads (ledger_reports.gather_
postings) so the T2125 ties to the trial balance. Personal side reads
PersonalTransaction with the same Python-side aggregation the personal
cashflow uses (amounts are encrypted; can't SUM in SQL).

Privacy: the personal half is returned only to the individual. An accountant
sees the business half and a note that the owner can export the full package.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports, tax_return
from app.accounting.ledger_models import AccountType
from app.auth.models import Role, User
from app.filing import t2125_lines as L
from app.filing.schemas import (
    FilingPackage,
    ReadinessItem,
    T1LineOut,
    T1PersonalSummary,
    T2125LineOut,
    T2125Statement,
)
from app.personal import service as personal
from app.settings.service import get_company_settings

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
GST_SMALL_SUPPLIER_THRESHOLD = Decimal("30000")

T1_LABELS: dict[str, str] = {
    "20800": "RRSP deduction",
    "21200": "Annual union, professional or like dues",
    "21400": "Child care expenses",
    "32300": "Tuition, education and textbook amounts",
    "33099": "Medical expenses for self, spouse, dependants",
    "34900": "Donations and gifts",
}


def _q(v) -> Decimal:
    return (v if isinstance(v, Decimal) else Decimal(str(v or 0))).quantize(Decimal("0.01"))


def fiscal_period(fye_month: int | None, year: int) -> tuple[date, date, int]:
    """(start, end, fye_month) for the fiscal year ENDING in ``year``.
    Sole props are calendar-year (12). A June year-end for 2026 is
    2025-07-01 → 2026-06-30."""
    m = fye_month or 12
    if m == 12:
        return date(year, 1, 1), date(year, 12, 31), 12
    end = date(year, m, calendar.monthrange(year, m)[1])
    start = date(year - 1, m + 1, 1)
    return start, end, m


# ---------------------------------------------------------------------------
# T2125
# ---------------------------------------------------------------------------


async def t2125_statement(db: AsyncSession, user: User, year: int) -> T2125Statement:
    company = await get_company_settings(db)
    start, end, fye = fiscal_period(company.fiscal_year_end_month if company else None, year)

    postings = await ledger_reports.gather_postings(db, user, date_from=start, date_to=end)
    pl = ledger_reports.profit_loss(postings)

    gross_sales = other_income = ZERO
    for row in pl["income"]:
        line = L.resolve_income_line(row["code"], row["name"])
        if line == "8230":
            other_income += _q(row["amount"])
        else:
            gross_sales += _q(row["amount"])

    by_line: dict[str, dict] = {}
    excluded: list[dict] = []
    unmapped: list[dict] = []
    cogs = ZERO
    for row in pl["expenses"]:
        amt = _q(row["amount"])
        src = {"code": row["code"], "name": row["name"], "amount": amt}
        if L.is_non_deductible(row["name"]):
            excluded.append(src)
            continue
        line, explicit = L.resolve_expense_line(row["code"], row["name"])
        if not explicit:
            unmapped.append(src)
        bucket = by_line.setdefault(line, {"amount": ZERO, "sources": []})
        bucket["amount"] += amt
        bucket["sources"].append(src)
        if L.LINES[line].part == "3C cogs":
            cogs += amt

    lines: list[T2125LineOut] = []
    total_allowable = ZERO
    for line_no, spec in L.LINES.items():
        b = by_line.get(line_no)
        amt = _q(b["amount"]) if b else ZERO
        if spec.computed and not b:
            # Always surface the computed lines so the accountant sees the gap.
            lines.append(T2125LineOut(line=line_no, label=spec.label, part=spec.part,
                                      amount=ZERO, allowable=ZERO, computed=True))
            continue
        if not b:
            continue
        allow = L.allowable(line_no, amt)
        if spec.part == "4 expenses":
            total_allowable += allow
        lines.append(T2125LineOut(line=line_no, label=spec.label, part=spec.part,
                                  amount=amt, allowable=allow, sources=b["sources"], computed=spec.computed))

    gross_income = _q(gross_sales + other_income)
    gross_profit = _q(gross_income - cogs)
    net_income = _q(gross_profit - total_allowable)

    gst = None
    try:
        gst = await tax_return.gst_hst_return(db, user, date_from=start, date_to=end)
    except Exception:  # noqa: BLE001 — GST block is informational
        logger.exception("filing: GST34 block failed")

    return T2125Statement(
        year=year, period_start=start, period_end=end, fiscal_year_end_month=fye,
        gross_sales=gross_sales, other_income=other_income, gross_income=gross_income,
        cost_of_goods_sold=_q(cogs), gross_profit=gross_profit,
        lines=lines, total_expenses=_q(total_allowable), net_income=net_income,
        excluded_non_deductible=excluded, unmapped=unmapped, gst_hst=gst,
    )


# ---------------------------------------------------------------------------
# T1 (personal)
# ---------------------------------------------------------------------------


async def t1_personal_summary(db: AsyncSession, user: User, year: int, net_business: Decimal) -> T1PersonalSummary:
    start, end = date(year, 1, 1), date(year, 12, 31)   # T1 is always calendar-year
    txns = await personal.list_transactions(db, user, date_from=start, date_to=end, limit=100_000)
    cats = {c.id: c for c in await personal.list_categories(db, user)}

    total_in = total_out = uncategorized_out = ZERO
    by_line: dict[str, dict] = {}
    for t in txns:
        amt = _q(t.amount)
        if t.direction == "in":
            total_in += amt
            continue
        total_out += amt
        cat = cats.get(t.category_id) if t.category_id else None
        t1 = getattr(cat, "t1_line", None) if cat else None
        if t1:
            b = by_line.setdefault(t1, {"amount": ZERO, "count": 0})
            b["amount"] += amt
            b["count"] += 1
        else:
            uncategorized_out += amt

    lines = [
        T1LineOut(line=ln, label=T1_LABELS.get(ln, ln), amount=_q(b["amount"]), transaction_count=b["count"])
        for ln, b in sorted(by_line.items())
    ]
    return T1PersonalSummary(
        year=year, total_in=_q(total_in), total_out=_q(total_out),
        net_business_income_line_13500=_q(net_business), lines=lines,
        uncategorized_out=_q(uncategorized_out),
    )


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


async def readiness(db: AsyncSession, user: User, year: int, t2125: T2125Statement, company) -> list[ReadinessItem]:
    items: list[ReadinessItem] = []

    def add(key, status, label, detail=None, path=None):
        items.append(ReadinessItem(key=key, status=status, label=label, detail=detail, action_path=path))

    if company and company.province:
        add("province", "ok", f"Province set: {company.province}")
    else:
        add("province", "todo", "Set your province", "Drives GST/HST/PST and the provincial tax return.", "/settings")

    if company and company.business_number:
        add("bn", "ok", f"CRA Business Number on file: {company.business_number}")
    else:
        add("bn", "todo", "Add your CRA Business Number", "Printed on the T2125, T4s and GST34.", "/settings")

    registered = bool(company and company.gst_hst_number)
    if registered:
        add("gst", "ok", f"GST/HST registered: {company.gst_hst_number}")
    elif t2125.gross_income >= GST_SMALL_SUPPLIER_THRESHOLD:
        add("gst", "warn", "GST/HST registration required",
            f"Gross income {t2125.gross_income:,.2f} is over the $30,000 small-supplier threshold. Register within 29 days of crossing it.", "/settings")
    else:
        add("gst", "info", "Under the $30,000 small-supplier threshold", "GST/HST registration is optional until you cross it.")

    if t2125.gst_hst and t2125.gst_hst.get("has_recorded_tax"):
        net = t2125.gst_hst.get("line_109_net_tax")
        add("gst34", "info", f"GST/HST net for the period: {net}", "Line 109 — positive means you owe CRA.")

    if t2125.unmapped:
        add("unmapped", "warn", f"{len(t2125.unmapped)} expense account(s) landed on line 9270 Other",
            "Rename the category or add a matching chart-of-accounts code so it maps to the right T2125 line.",
            "/accounting/chart-of-accounts")
    else:
        add("unmapped", "ok", "Every expense mapped to a T2125 line")

    if t2125.excluded_non_deductible:
        add("nondeductible", "info", f"{len(t2125.excluded_non_deductible)} non-deductible item(s) excluded",
            ", ".join(f"{s['name']} ({s['amount']:,.2f})" for s in t2125.excluded_non_deductible[:4]))

    add("cca", "todo", "Capital cost allowance (line 9936) not computed",
        "Depreciation in the books is not CCA. Your accountant computes CCA by asset class.")
    add("home", "todo", "Business-use-of-home (line 9945) not computed",
        "Needs your home office square footage as a % of the home. Not in the ledger.")

    # Payroll: T4s owed?
    try:
        from app.payroll import service as payroll_svc

        emps = await payroll_svc.list_employees(db, user, include_terminated=True)
        with_pay = []
        for e in emps:
            y = await payroll_svc.employee_ytd(db, user, e.id, year=year)
            if y.stub_count:
                with_pay.append(e)
        if with_pay:
            add("t4", "todo", f"Issue {len(with_pay)} T4 slip(s) for {year}",
                "Due to employees and CRA by the last day of February.", "/payroll/employees")
    except Exception:  # noqa: BLE001
        logger.exception("filing: payroll readiness failed")

    return items


# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------


async def filing_package(db: AsyncSession, user: User, year: int) -> FilingPackage:
    company = await get_company_settings(db)
    t2125 = await t2125_statement(db, user, year)

    # Personal half: owner only. An accountant's own personal ledger is not the
    # client's, so never present it as if it were.
    include_personal = user.role != Role.ACCOUNTANT
    t1 = await t1_personal_summary(db, user, year, t2125.net_income) if include_personal else None

    items = await readiness(db, user, year, t2125, company)
    if not include_personal:
        items.append(ReadinessItem(
            key="personal", status="info",
            label="Personal (T1) half not included",
            detail="Only the business owner can see their personal ledger. Ask them to export the full package.",
        ))

    return FilingPackage(
        year=year,
        business_name=company.company_name if company else None,
        province=company.province if company else None,
        business_number=company.business_number if company else None,
        gst_hst_number=company.gst_hst_number if company else None,
        generated_at=date.today(),
        personal_included=include_personal,
        t2125=t2125, t1=t1, readiness=items,
    )
