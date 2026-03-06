
from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseCategory
from app.income.models import Income, IncomeCategory
from app.invoicing.models import Invoice, InvoicePayment, InvoiceStatus
from app.contacts.models import Contact
from app.reports.schemas import (
    AccountsSummary,
    AgingBucket,
    AgingBucketTotals,
    AgingReport,
    CashFlowPeriod,
    CashFlowReport,
    CategoryAmount,
    ProfitLossReport,
    QuarterlyBreakdown,
    QuarterlyTaxReport,
    TaxDeadline,
    TaxSummary,
    YearOverYearComparison,
)


async def get_profit_loss(
    db: AsyncSession, date_from: date, date_to: date
) -> ProfitLossReport:
    # Income by category
    income_q = (
        select(Income.category, func.coalesce(func.sum(Income.amount), 0))
        .where(Income.date.between(date_from, date_to))
        .group_by(Income.category)
    )
    income_rows = (await db.execute(income_q)).all()
    income_by_cat = [
        CategoryAmount(category=r[0].value.replace("_", " ").title(), amount=float(r[1]))
        for r in income_rows
    ]
    total_income = sum(c.amount for c in income_by_cat)

    # Expenses by category
    expense_q = (
        select(
            func.coalesce(ExpenseCategory.name, "Uncategorized"),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(Expense.date.between(date_from, date_to))
        .group_by(ExpenseCategory.name)
    )
    expense_rows = (await db.execute(expense_q)).all()
    expenses_by_cat = [
        CategoryAmount(category=r[0], amount=float(r[1]))
        for r in expense_rows
    ]
    total_expenses = sum(c.amount for c in expenses_by_cat)

    return ProfitLossReport(
        date_from=date_from,
        date_to=date_to,
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=total_income - total_expenses,
        income_by_category=income_by_cat,
        expenses_by_category=expenses_by_cat,
    )


async def get_tax_summary(db: AsyncSession, year: int) -> TaxSummary:
    # Total income for year
    income_q = select(func.coalesce(func.sum(Income.amount), 0)).where(
        extract("year", Income.date) == year
    )
    taxable_income = float((await db.execute(income_q)).scalar() or 0)

    # Total expenses for year
    expense_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        extract("year", Expense.date) == year
    )
    deductible_expenses = float((await db.execute(expense_q)).scalar() or 0)

    # Tax collected on invoices (paid/partially_paid invoices)
    tax_q = select(func.coalesce(func.sum(Invoice.tax_amount), 0)).where(
        extract("year", Invoice.issue_date) == year,
        Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.tax_amount.isnot(None),
    )
    tax_collected = float((await db.execute(tax_q)).scalar() or 0)

    return TaxSummary(
        year=year,
        taxable_income=taxable_income,
        deductible_expenses=deductible_expenses,
        tax_collected=tax_collected,
        net_taxable=taxable_income - deductible_expenses,
    )


async def get_cash_flow(
    db: AsyncSession, date_from: date, date_to: date
) -> CashFlowReport:
    # Income by month
    income_q = (
        select(
            extract("year", Income.date).label("y"),
            extract("month", Income.date).label("m"),
            func.coalesce(func.sum(Income.amount), 0),
        )
        .where(Income.date.between(date_from, date_to))
        .group_by("y", "m")
        .order_by("y", "m")
    )
    income_rows = {(int(r[0]), int(r[1])): float(r[2]) for r in (await db.execute(income_q)).all()}

    # Expenses by month
    expense_q = (
        select(
            extract("year", Expense.date).label("y"),
            extract("month", Expense.date).label("m"),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .where(Expense.date.between(date_from, date_to))
        .group_by("y", "m")
        .order_by("y", "m")
    )
    expense_rows = {(int(r[0]), int(r[1])): float(r[2]) for r in (await db.execute(expense_q)).all()}

    # Merge into periods
    all_months = set(income_rows.keys()) | set(expense_rows.keys())
    periods = []
    for ym in sorted(all_months):
        y, m = ym
        inc = income_rows.get(ym, 0)
        exp = expense_rows.get(ym, 0)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        label = f"{month_names[m - 1]} {y}"
        periods.append(CashFlowPeriod(period_label=label, income=inc, expenses=exp, net=inc - exp))

    return CashFlowReport(date_from=date_from, date_to=date_to, periods=periods)


async def get_accounts_summary(db: AsyncSession) -> AccountsSummary:
    today = date.today()

    # Total receivable: unpaid invoices
    recv_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status.in_([
            InvoiceStatus.SENT, InvoiceStatus.VIEWED,
            InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE,
        ])
    )
    total_receivable = float((await db.execute(recv_q)).scalar() or 0)

    # Subtract partial payments from receivable
    partial_q = (
        select(func.coalesce(func.sum(InvoicePayment.amount), 0))
        .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
        .where(Invoice.status.in_([InvoiceStatus.PARTIALLY_PAID]))
    )
    partial_paid = float((await db.execute(partial_q)).scalar() or 0)
    total_receivable -= partial_paid

    # Overdue receivable
    overdue_q = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    overdue_receivable = float((await db.execute(overdue_q)).scalar() or 0)

    # Total payable (pending/approved expenses)
    payable_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.status.in_(["pending_review", "approved"])
    )
    total_payable = float((await db.execute(payable_q)).scalar() or 0)

    return AccountsSummary(
        total_receivable=total_receivable,
        total_payable=total_payable,
        overdue_receivable=overdue_receivable,
        net_position=total_receivable - total_payable,
    )


def _classify_days_overdue(days_overdue: int) -> str:
    """Return the bucket key for a given number of days overdue."""
    if days_overdue <= 0:
        return "current"
    elif days_overdue <= 30:
        return "days_1_30"
    elif days_overdue <= 60:
        return "days_31_60"
    elif days_overdue <= 90:
        return "days_61_90"
    else:
        return "days_90_plus"


def _empty_buckets() -> dict[str, float]:
    return {
        "current": 0.0,
        "days_1_30": 0.0,
        "days_31_60": 0.0,
        "days_61_90": 0.0,
        "days_90_plus": 0.0,
    }


async def get_ar_aging(db: AsyncSession, as_of_date: date) -> AgingReport:
    """Accounts Receivable aging: outstanding invoices grouped by contact and age bucket."""

    # Fetch unpaid / partially paid invoices with their contacts
    q = (
        select(
            Invoice.id,
            Invoice.due_date,
            Invoice.total,
            Invoice.status,
            Contact.company_name,
        )
        .join(Contact, Invoice.contact_id == Contact.id)
        .where(
            Invoice.status.in_([
                InvoiceStatus.SENT,
                InvoiceStatus.VIEWED,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.OVERDUE,
            ])
        )
    )
    rows = (await db.execute(q)).all()

    # Build a map of partial payments per invoice
    payment_q = (
        select(
            InvoicePayment.invoice_id,
            func.coalesce(func.sum(InvoicePayment.amount), 0),
        )
        .group_by(InvoicePayment.invoice_id)
    )
    payment_rows = (await db.execute(payment_q)).all()
    payments_by_invoice: dict[str, float] = {
        str(r[0]): float(r[1]) for r in payment_rows
    }

    # Group by contact
    contact_buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        invoice_id, due_date_val, total, status, company_name = row
        outstanding = float(total) - payments_by_invoice.get(str(invoice_id), 0.0)
        if outstanding <= 0:
            continue
        days_overdue = (as_of_date - due_date_val).days
        bucket_key = _classify_days_overdue(days_overdue)
        if company_name not in contact_buckets:
            contact_buckets[company_name] = _empty_buckets()
        contact_buckets[company_name][bucket_key] += outstanding

    # Build response
    buckets: list[AgingBucket] = []
    grand = _empty_buckets()
    for name in sorted(contact_buckets.keys()):
        b = contact_buckets[name]
        row_total = sum(b.values())
        buckets.append(AgingBucket(name=name, total=row_total, **b))
        for key in grand:
            grand[key] += b[key]

    grand_total = sum(grand.values())
    return AgingReport(
        as_of_date=as_of_date,
        buckets=buckets,
        grand_totals=AgingBucketTotals(total=grand_total, **grand),
    )


async def get_ap_aging(db: AsyncSession, as_of_date: date) -> AgingReport:
    """Accounts Payable aging: outstanding expenses grouped by vendor and age bucket."""

    # Fetch unpaid expenses (pending_review or approved)
    q = (
        select(
            Expense.id,
            Expense.date,
            Expense.amount,
            func.coalesce(Expense.vendor_name, "Unknown Vendor"),
        )
        .where(Expense.status.in_(["pending_review", "approved"]))
    )
    rows = (await db.execute(q)).all()

    # Group by vendor
    vendor_buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        _expense_id, expense_date, amount, vendor_name = row
        days_overdue = (as_of_date - expense_date).days
        bucket_key = _classify_days_overdue(days_overdue)
        if vendor_name not in vendor_buckets:
            vendor_buckets[vendor_name] = _empty_buckets()
        vendor_buckets[vendor_name][bucket_key] += float(amount)

    # Build response
    buckets: list[AgingBucket] = []
    grand = _empty_buckets()
    for name in sorted(vendor_buckets.keys()):
        b = vendor_buckets[name]
        row_total = sum(b.values())
        buckets.append(AgingBucket(name=name, total=row_total, **b))
        for key in grand:
            grand[key] += b[key]

    grand_total = sum(grand.values())
    return AgingReport(
        as_of_date=as_of_date,
        buckets=buckets,
        grand_totals=AgingBucketTotals(total=grand_total, **grand),
    )


# ---------------------------------------------------------------------------
# Quarterly Tax Report helpers
# ---------------------------------------------------------------------------

QUARTER_RANGES = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
QUARTER_LABELS = {1: "Q1 (Jan-Mar)", 2: "Q2 (Apr-Jun)", 3: "Q3 (Jul-Sep)", 4: "Q4 (Oct-Dec)"}
TAX_DEADLINES = {1: "April 15", 2: "June 15", 3: "September 15", 4: "January 15"}
TAX_DEADLINE_DATES = {1: (4, 15), 2: (6, 15), 3: (9, 15), 4: (1, 15)}


async def get_quarterly_tax_report(
    db: AsyncSession, year: int, tax_rate: float = 25.0
) -> QuarterlyTaxReport:
    today = date.today()
    quarters: list[QuarterlyBreakdown] = []

    for q in range(1, 5):
        start_month, end_month = QUARTER_RANGES[q]

        # Income for this quarter
        income_q = select(func.coalesce(func.sum(Income.amount), 0)).where(
            extract("year", Income.date) == year,
            extract("month", Income.date) >= start_month,
            extract("month", Income.date) <= end_month,
        )
        quarter_income = float((await db.execute(income_q)).scalar() or 0)

        # Expenses for this quarter
        expense_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(
            extract("year", Expense.date) == year,
            extract("month", Expense.date) >= start_month,
            extract("month", Expense.date) <= end_month,
        )
        quarter_expenses = float((await db.execute(expense_q)).scalar() or 0)

        # Tax collected on paid/partially_paid invoices this quarter
        tax_q = select(func.coalesce(func.sum(Invoice.tax_amount), 0)).where(
            extract("year", Invoice.issue_date) == year,
            extract("month", Invoice.issue_date) >= start_month,
            extract("month", Invoice.issue_date) <= end_month,
            Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.tax_amount.isnot(None),
        )
        quarter_tax = float((await db.execute(tax_q)).scalar() or 0)

        net = quarter_income - quarter_expenses
        estimated_tax = net * tax_rate / 100.0

        # Determine if the deadline is overdue
        dl_month, dl_day = TAX_DEADLINE_DATES[q]
        dl_year = year + 1 if q == 4 else year
        deadline_date = date(dl_year, dl_month, dl_day)
        is_overdue = today > deadline_date

        quarters.append(
            QuarterlyBreakdown(
                quarter=q,
                quarter_label=QUARTER_LABELS[q],
                income=quarter_income,
                expenses=quarter_expenses,
                net=net,
                tax_collected=quarter_tax,
                estimated_tax=estimated_tax,
                deadline=TAX_DEADLINES[q],
                is_overdue=is_overdue,
            )
        )

    # Annual totals
    annual_income = sum(qb.income for qb in quarters)
    annual_expenses = sum(qb.expenses for qb in quarters)
    annual_net = annual_income - annual_expenses
    annual_tax_collected = sum(qb.tax_collected for qb in quarters)
    annual_estimated_tax = sum(qb.estimated_tax for qb in quarters)

    # Income by category (full year)
    income_cat_q = (
        select(Income.category, func.coalesce(func.sum(Income.amount), 0))
        .where(extract("year", Income.date) == year)
        .group_by(Income.category)
    )
    income_cat_rows = (await db.execute(income_cat_q)).all()
    income_by_cat = [
        CategoryAmount(category=r[0].value.replace("_", " ").title(), amount=float(r[1]))
        for r in income_cat_rows
    ]

    # Expenses by category (full year)
    expense_cat_q = (
        select(
            func.coalesce(ExpenseCategory.name, "Uncategorized"),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(extract("year", Expense.date) == year)
        .group_by(ExpenseCategory.name)
    )
    expense_cat_rows = (await db.execute(expense_cat_q)).all()
    expenses_by_cat = [
        CategoryAmount(category=r[0], amount=float(r[1]))
        for r in expense_cat_rows
    ]

    return QuarterlyTaxReport(
        year=year,
        tax_rate=tax_rate,
        quarters=quarters,
        annual_total_income=annual_income,
        annual_total_expenses=annual_expenses,
        annual_net=annual_net,
        annual_tax_collected=annual_tax_collected,
        annual_estimated_tax=annual_estimated_tax,
        income_by_category=income_by_cat,
        expenses_by_category=expenses_by_cat,
    )


async def get_year_over_year(db: AsyncSession, year: int) -> YearOverYearComparison:
    prev = year - 1

    # Current year income
    cur_inc_q = select(func.coalesce(func.sum(Income.amount), 0)).where(
        extract("year", Income.date) == year
    )
    current_income = float((await db.execute(cur_inc_q)).scalar() or 0)

    # Previous year income
    prev_inc_q = select(func.coalesce(func.sum(Income.amount), 0)).where(
        extract("year", Income.date) == prev
    )
    previous_income = float((await db.execute(prev_inc_q)).scalar() or 0)

    # Current year expenses
    cur_exp_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        extract("year", Expense.date) == year
    )
    current_expenses = float((await db.execute(cur_exp_q)).scalar() or 0)

    # Previous year expenses
    prev_exp_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        extract("year", Expense.date) == prev
    )
    previous_expenses = float((await db.execute(prev_exp_q)).scalar() or 0)

    # Change percentages (None if previous is 0)
    income_change_pct = (
        ((current_income - previous_income) / previous_income * 100.0)
        if previous_income != 0
        else None
    )
    expenses_change_pct = (
        ((current_expenses - previous_expenses) / previous_expenses * 100.0)
        if previous_expenses != 0
        else None
    )

    return YearOverYearComparison(
        current_year=year,
        previous_year=prev,
        current_income=current_income,
        previous_income=previous_income,
        income_change_pct=income_change_pct,
        current_expenses=current_expenses,
        previous_expenses=previous_expenses,
        expenses_change_pct=expenses_change_pct,
        current_net=current_income - current_expenses,
        previous_net=previous_income - previous_expenses,
    )


def get_tax_deadlines(year: int) -> list[TaxDeadline]:
    today = date.today()
    deadlines: list[TaxDeadline] = []

    for q in range(1, 5):
        dl_month, dl_day = TAX_DEADLINE_DATES[q]
        dl_year = year + 1 if q == 4 else year
        deadline_date = date(dl_year, dl_month, dl_day)
        is_past = today > deadline_date
        delta = (deadline_date - today).days
        days_until = None if is_past else delta

        deadlines.append(
            TaxDeadline(
                quarter=q,
                quarter_label=QUARTER_LABELS[q],
                deadline_date=deadline_date.isoformat(),
                description=f"Estimated tax payment for {QUARTER_LABELS[q]} {year}",
                is_past=is_past,
                days_until=days_until,
            )
        )

    return deadlines
