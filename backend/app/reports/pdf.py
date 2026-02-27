from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.schemas import ProfitLossReport, TaxSummary


def _build_doc(buffer):
    return SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )


def _header_style():
    styles = getSampleStyleSheet()
    return ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#1e3a5f"))


def generate_profit_loss_pdf(report: ProfitLossReport, business_name: str = "Accountant") -> bytes:
    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    styles = getSampleStyleSheet()
    elements: list = []

    elements.append(Paragraph(business_name, _header_style()))
    elements.append(Paragraph(
        f"Profit & Loss Report: {report.date_from} to {report.date_to}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))

    # Income section
    elements.append(Paragraph("<b>Income</b>", styles["Heading2"]))
    if report.income_by_category:
        inc_data = [["Category", "Amount"]]
        for c in report.income_by_category:
            inc_data.append([c.category, f"${c.amount:,.2f}"])
        inc_data.append(["Total Income", f"${report.total_income:,.2f}"])
        t = Table(inc_data, colWidths=[4 * inch, 3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No income recorded.", styles["Normal"]))

    elements.append(Spacer(1, 16))

    # Expenses section
    elements.append(Paragraph("<b>Expenses</b>", styles["Heading2"]))
    if report.expenses_by_category:
        exp_data = [["Category", "Amount"]]
        for c in report.expenses_by_category:
            exp_data.append([c.category, f"${c.amount:,.2f}"])
        exp_data.append(["Total Expenses", f"${report.total_expenses:,.2f}"])
        t = Table(exp_data, colWidths=[4 * inch, 3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No expenses recorded.", styles["Normal"]))

    elements.append(Spacer(1, 20))

    # Net profit
    color = colors.green if report.net_profit >= 0 else colors.red
    net_style = ParagraphStyle("NetProfit", parent=styles["Heading1"], textColor=color, fontSize=16)
    elements.append(Paragraph(f"Net Profit: ${report.net_profit:,.2f}", net_style))

    doc.build(elements)
    return buffer.getvalue()


def generate_tax_summary_pdf(report: TaxSummary, business_name: str = "Accountant") -> bytes:
    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    styles = getSampleStyleSheet()
    elements: list = []

    elements.append(Paragraph(business_name, _header_style()))
    elements.append(Paragraph(f"Tax Summary — {report.year}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    data = [
        ["Item", "Amount"],
        ["Taxable Income", f"${report.taxable_income:,.2f}"],
        ["Deductible Expenses", f"${report.deductible_expenses:,.2f}"],
        ["Tax Collected (Invoices)", f"${report.tax_collected:,.2f}"],
        ["Net Taxable Amount", f"${report.net_taxable:,.2f}"],
    ]
    t = Table(data, colWidths=[4 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    doc.build(elements)
    return buffer.getvalue()
