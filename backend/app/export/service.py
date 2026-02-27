
import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# CSV Export (QuickBooks-compatible)
# ---------------------------------------------------------------------------


async def export_to_csv(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    include: str,
) -> str:
    """Generate a QuickBooks-compatible CSV export."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Type", "Date", "Num", "Name", "Memo/Description",
        "Account", "Amount", "Currency",
    ])

    if include in ("expenses", "all"):
        await _write_expenses_csv(db, writer, date_from, date_to)

    if include in ("income", "all"):
        await _write_income_csv(db, writer, date_from, date_to)

    if include in ("invoices", "all"):
        await _write_invoices_csv(db, writer, date_from, date_to)

    return output.getvalue()


async def _write_expenses_csv(
    db: AsyncSession,
    writer: csv.writer,
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.accounting.models import Expense

    stmt = select(Expense).order_by(Expense.date)
    if date_from:
        stmt = stmt.where(Expense.date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.date <= date_to)

    result = await db.execute(stmt)
    for exp in result.scalars().all():
        writer.writerow([
            "Expense",
            exp.date.isoformat(),
            "",
            exp.vendor_name or "",
            exp.description or "",
            "Expenses",
            f"-{exp.amount:.2f}",
            exp.currency,
        ])


async def _write_income_csv(
    db: AsyncSession,
    writer: csv.writer,
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.income.models import Income

    stmt = select(Income).order_by(Income.date)
    if date_from:
        stmt = stmt.where(Income.date >= date_from)
    if date_to:
        stmt = stmt.where(Income.date <= date_to)

    result = await db.execute(stmt)
    for inc in result.scalars().all():
        writer.writerow([
            "Income",
            inc.date.isoformat(),
            "",
            "",
            inc.description or "",
            "Income",
            f"{inc.amount:.2f}",
            inc.currency,
        ])


async def _write_invoices_csv(
    db: AsyncSession,
    writer: csv.writer,
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.invoicing.models import Invoice

    stmt = select(Invoice).order_by(Invoice.issue_date)
    if date_from:
        stmt = stmt.where(Invoice.issue_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.issue_date <= date_to)

    result = await db.execute(stmt)
    for inv in result.scalars().all():
        contact_name = ""
        if hasattr(inv, "contact") and inv.contact:
            contact_name = inv.contact.name
        writer.writerow([
            "Invoice",
            inv.issue_date.isoformat(),
            inv.invoice_number,
            contact_name,
            inv.notes or "",
            "Accounts Receivable",
            f"{inv.total:.2f}",
            inv.currency,
        ])


# ---------------------------------------------------------------------------
# IIF Export (Intuit Interchange Format)
# ---------------------------------------------------------------------------


async def export_to_iif(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    include: str,
) -> str:
    """Generate an IIF (Intuit Interchange Format) file for QuickBooks import."""
    lines: list[str] = []

    if include in ("expenses", "all"):
        await _write_expenses_iif(db, lines, date_from, date_to)

    if include in ("income", "all"):
        await _write_income_iif(db, lines, date_from, date_to)

    if include in ("invoices", "all"):
        await _write_invoices_iif(db, lines, date_from, date_to)

    return "\n".join(lines) + "\n" if lines else ""


async def _write_expenses_iif(
    db: AsyncSession,
    lines: list[str],
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.accounting.models import Expense

    stmt = select(Expense).order_by(Expense.date)
    if date_from:
        stmt = stmt.where(Expense.date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.date <= date_to)

    result = await db.execute(stmt)
    for exp in result.scalars().all():
        date_str = exp.date.strftime("%m/%d/%Y")
        memo = (exp.description or "").replace("\t", " ")
        name = (exp.vendor_name or "").replace("\t", " ")

        lines.append(f"!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!ENDTRNS")
        lines.append(f"TRNS\tCHECK\t{date_str}\tChecking\t{name}\t-{exp.amount:.2f}\t{memo}")
        lines.append(f"SPL\tCHECK\t{date_str}\tExpenses\t{name}\t{exp.amount:.2f}\t{memo}")
        lines.append("ENDTRNS")


async def _write_income_iif(
    db: AsyncSession,
    lines: list[str],
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.income.models import Income

    stmt = select(Income).order_by(Income.date)
    if date_from:
        stmt = stmt.where(Income.date >= date_from)
    if date_to:
        stmt = stmt.where(Income.date <= date_to)

    result = await db.execute(stmt)
    for inc in result.scalars().all():
        date_str = inc.date.strftime("%m/%d/%Y")
        memo = (inc.description or "").replace("\t", " ")

        lines.append(f"!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!ENDTRNS")
        lines.append(f"TRNS\tDEPOSIT\t{date_str}\tChecking\t\t{inc.amount:.2f}\t{memo}")
        lines.append(f"SPL\tDEPOSIT\t{date_str}\tIncome\t\t-{inc.amount:.2f}\t{memo}")
        lines.append("ENDTRNS")


async def _write_invoices_iif(
    db: AsyncSession,
    lines: list[str],
    date_from: date | None,
    date_to: date | None,
) -> None:
    from app.invoicing.models import Invoice

    stmt = select(Invoice).order_by(Invoice.issue_date)
    if date_from:
        stmt = stmt.where(Invoice.issue_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.issue_date <= date_to)

    result = await db.execute(stmt)
    for inv in result.scalars().all():
        date_str = inv.issue_date.strftime("%m/%d/%Y")
        contact_name = ""
        if hasattr(inv, "contact") and inv.contact:
            contact_name = inv.contact.name.replace("\t", " ")
        memo = (inv.notes or "").replace("\t", " ")

        lines.append(f"!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
        lines.append(f"!ENDTRNS")
        lines.append(f"TRNS\tINVOICE\t{date_str}\tAccounts Receivable\t{contact_name}\t{inv.total:.2f}\t{memo}")
        lines.append(f"SPL\tINVOICE\t{date_str}\tIncome\t{contact_name}\t-{inv.total:.2f}\t{memo}")
        lines.append("ENDTRNS")


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------


async def export_chart_of_accounts() -> str:
    """Export a basic chart of accounts in CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Account Name", "Account Type", "Description"])

    accounts = [
        ("Checking", "Bank", "Primary checking account"),
        ("Savings", "Bank", "Savings account"),
        ("Accounts Receivable", "Accounts Receivable", "Money owed to the business"),
        ("Income", "Income", "Revenue from services and products"),
        ("Expenses", "Expense", "General business expenses"),
        ("Cost of Goods Sold", "Cost of Goods Sold", "Direct costs of products/services"),
        ("Accounts Payable", "Accounts Payable", "Money owed to vendors"),
        ("Credit Card", "Credit Card", "Business credit card"),
        ("Payroll Expenses", "Expense", "Employee wages and benefits"),
        ("Office Supplies", "Expense", "Office supplies and materials"),
        ("Travel", "Expense", "Business travel expenses"),
        ("Professional Fees", "Expense", "Legal, accounting, consulting fees"),
        ("Utilities", "Expense", "Utilities and telephone"),
        ("Rent", "Expense", "Office rent"),
        ("Insurance", "Expense", "Business insurance"),
        ("Taxes", "Expense", "Business taxes"),
    ]

    for name, acct_type, desc in accounts:
        writer.writerow([name, acct_type, desc])

    return output.getvalue()
