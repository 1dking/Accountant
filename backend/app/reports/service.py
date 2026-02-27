from __future__ import annotations

from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseCategory
from app.income.models import Income, IncomeCategory
from app.invoicing.models import Invoice, InvoicePayment, InvoiceStatus
from app.reports.schemas import (
    AccountsSummary,
    CashFlowPeriod,
    CashFlowReport,
    CategoryAmount,
    ProfitLossReport,
    TaxSummary,
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
