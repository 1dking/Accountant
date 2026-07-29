"""PDF export for the cashbook-consistent Financial Statements.

Unlike app/reports/pdf.py (which renders the legacy Income/Expense-table
reports), these render the double-entry P&L and Balance Sheet produced by
app.accounting.ledger_reports — the statements that tie to the cashbook and, in
the Balance Sheet's case, actually balance. This is what an owner hands to their
accountant or bank.

Both take the dicts returned by ledger_reports.profit_loss / .balance_sheet
(amounts are Decimal) plus the period and a business name.
"""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_INK = colors.HexColor("#1e3a5f")
_RULE = colors.HexColor("#cbd5e1")
_BAND = colors.HexColor("#f1f5f9")
_MUTED = colors.HexColor("#64748b")
_ZERO = Decimal("0")


def _money(amount) -> str:
    """Accounting format: negatives in parentheses, thousands separators."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount or 0))
    if d < 0:
        return f"(${-d:,.2f})"
    return f"${d:,.2f}"


def _doc(buffer):
    return SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
    )


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("StmtBusiness", parent=s["Title"], fontSize=18, textColor=_INK, spaceAfter=2))
    s.add(ParagraphStyle("StmtTitle", parent=s["Heading2"], fontSize=13, textColor=_INK, spaceBefore=0, spaceAfter=1))
    s.add(ParagraphStyle("StmtPeriod", parent=s["Normal"], fontSize=9.5, textColor=_MUTED))
    s.add(ParagraphStyle("StmtSection", parent=s["Heading3"], fontSize=10.5, textColor=_INK, spaceBefore=10, spaceAfter=2))
    return s


def _line_table(rows: list, *, total_label: str, total_amount, code_col: bool = True):
    """A section: itemized `[code, name, amount]` lines then a bold total rule."""
    data = []
    for r in rows:
        name = r["name"]
        if code_col and r.get("code"):
            name = f"{r['code']}  {name}"
        data.append([name, _money(r["amount"])])
    data.append([total_label, _money(total_amount)])
    if len(data) == 1:  # only the total row -> nothing itemized
        data.insert(0, ["No activity in this period", ""])

    t = Table(data, colWidths=[4.7 * inch, 1.9 * inch], hAlign="LEFT")
    last = len(data) - 1
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        # total row
        ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
        ("LINEABOVE", (0, last), (-1, last), 0.75, _RULE),
        ("TOPPADDING", (0, last), (-1, last), 5),
    ]))
    return t


def _kpi_row(label: str, amount, *, emphatic=False):
    """A single emphasized figure (Net Profit, In-balance check)."""
    color = _INK
    if emphatic:
        d = amount if isinstance(amount, Decimal) else Decimal(str(amount or 0))
        color = colors.HexColor("#15803d") if d >= 0 else colors.HexColor("#b91c1c")
    t = Table([[label, _money(amount)]], colWidths=[4.7 * inch, 1.9 * inch], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (0, 0), (-1, -1), color),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 1.4, _INK),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
    ]))
    return t


def _header(elements, styles, business_name, title, period_line):
    elements.append(Paragraph(business_name, styles["StmtBusiness"]))
    elements.append(Paragraph(title, styles["StmtTitle"]))
    elements.append(Paragraph(period_line, styles["StmtPeriod"]))
    elements.append(Spacer(1, 4))
    band = Table([[""]], colWidths=[6.6 * inch], rowHeights=[2])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _INK)]))
    elements.append(band)
    elements.append(Spacer(1, 10))


def generate_profit_loss_pdf(pl: dict, *, date_from, date_to, business_name: str = "Financial Statements") -> bytes:
    buffer = io.BytesIO()
    doc = _doc(buffer)
    styles = _styles()
    elements: list = []

    period = "Inception to date" if not date_from else f"{date_from} to {date_to or 'today'}"
    if date_from is None and date_to is not None:
        period = f"Through {date_to}"
    _header(elements, styles, business_name, "Profit & Loss (Income Statement)", period)

    elements.append(Paragraph("Income", styles["StmtSection"]))
    elements.append(_line_table(pl["income"], total_label="Total Income", total_amount=pl["total_income"]))

    elements.append(Paragraph("Expenses", styles["StmtSection"]))
    elements.append(_line_table(pl["expenses"], total_label="Total Expenses", total_amount=pl["total_expenses"]))

    elements.append(Spacer(1, 12))
    elements.append(_kpi_row("Net Profit", pl["net_profit"], emphatic=True))

    elements.append(Spacer(1, 18))
    elements.append(Paragraph(
        "Prepared from the cashbook on a double-entry basis. Figures tie to the "
        "Trial Balance and General Ledger.", styles["StmtPeriod"]))

    doc.build(elements)
    return buffer.getvalue()


def generate_balance_sheet_pdf(bs: dict, *, as_of, business_name: str = "Financial Statements") -> bytes:
    buffer = io.BytesIO()
    doc = _doc(buffer)
    styles = _styles()
    elements: list = []

    _header(elements, styles, business_name, "Balance Sheet", f"As of {as_of}")

    elements.append(Paragraph("Assets", styles["StmtSection"]))
    elements.append(_line_table(bs["assets"], total_label="Total Assets", total_amount=bs["total_assets"]))

    elements.append(Paragraph("Liabilities", styles["StmtSection"]))
    elements.append(_line_table(bs["liabilities"], total_label="Total Liabilities", total_amount=bs["total_liabilities"]))

    elements.append(Paragraph("Equity", styles["StmtSection"]))
    elements.append(_line_table(bs["equity"], total_label="Total Equity", total_amount=bs["total_equity"]))

    elements.append(Spacer(1, 12))
    elements.append(_kpi_row("Total Liabilities & Equity", bs["total_liabilities_equity"]))

    elements.append(Spacer(1, 10))
    balanced = bool(bs.get("balanced"))
    mark = "In balance  —  Assets = Liabilities + Equity" if balanced else \
        "OUT OF BALANCE — review opening balances"
    chip = Table([[mark]], colWidths=[6.6 * inch])
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7") if balanced else colors.HexColor("#fee2e2")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#166534") if balanced else colors.HexColor("#991b1b")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(chip)

    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "Prepared from the cashbook on a double-entry basis. Opening balances are "
        "folded in and the period's net income is closed to Retained Earnings.",
        styles["StmtPeriod"]))

    doc.build(elements)
    return buffer.getvalue()
