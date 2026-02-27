
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.invoicing.models import Invoice


def generate_invoice_pdf(invoice: Invoice, business_name: str = "Accountant") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvTitle", parent=styles["Title"], fontSize=24, textColor=colors.HexColor("#1e3a5f"))
    subtitle_style = ParagraphStyle("InvSub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    normal_style = styles["Normal"]

    elements: list = []

    # Header
    elements.append(Paragraph(business_name, title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Invoice #{invoice.invoice_number}", subtitle_style))
    elements.append(Spacer(1, 20))

    # Invoice details table
    contact = invoice.contact
    bill_to = contact.company_name if contact else "—"
    if contact and contact.contact_name:
        bill_to += f"<br/>{contact.contact_name}"
    if contact and contact.email:
        bill_to += f"<br/>{contact.email}"
    address_parts = []
    if contact:
        if contact.address_line1:
            address_parts.append(contact.address_line1)
        city_state = ", ".join(filter(None, [contact.city, contact.state]))
        if city_state:
            if contact.zip_code:
                city_state += f" {contact.zip_code}"
            address_parts.append(city_state)
    if address_parts:
        bill_to += "<br/>" + "<br/>".join(address_parts)

    info_data = [
        [Paragraph("<b>Bill To:</b>", normal_style), Paragraph("<b>Invoice Details:</b>", normal_style)],
        [
            Paragraph(bill_to, normal_style),
            Paragraph(
                f"Date: {invoice.issue_date}<br/>"
                f"Due: {invoice.due_date}<br/>"
                f"Status: {invoice.status.value.replace('_', ' ').title()}<br/>"
                f"Currency: {invoice.currency}",
                normal_style,
            ),
        ],
    ]
    info_table = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # Line items table
    header_row = ["Description", "Qty", "Unit Price", "Total"]
    table_data = [header_row]
    for li in invoice.line_items:
        table_data.append([
            li.description,
            f"{li.quantity:.2f}",
            f"${li.unit_price:,.2f}",
            f"${li.total:,.2f}",
        ])

    items_table = Table(table_data, colWidths=[3.5 * inch, 1 * inch, 1.25 * inch, 1.25 * inch])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 12))

    # Totals
    totals_data = [
        ["Subtotal:", f"${invoice.subtotal:,.2f}"],
    ]
    if invoice.tax_amount:
        rate_str = f" ({invoice.tax_rate}%)" if invoice.tax_rate else ""
        totals_data.append([f"Tax{rate_str}:", f"${invoice.tax_amount:,.2f}"])
    if invoice.discount_amount:
        totals_data.append(["Discount:", f"-${invoice.discount_amount:,.2f}"])
    totals_data.append(["Total:", f"${invoice.total:,.2f}"])

    totals_table = Table(totals_data, colWidths=[5.5 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#334155")),
    ]))
    elements.append(totals_table)

    # Payment history
    if invoice.payments:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Payment History</b>", normal_style))
        elements.append(Spacer(1, 6))
        pay_data = [["Date", "Amount", "Method", "Reference"]]
        for p in invoice.payments:
            pay_data.append([
                str(p.date),
                f"${p.amount:,.2f}",
                (p.payment_method or "—").replace("_", " ").title(),
                p.reference or "—",
            ])
        pay_table = Table(pay_data, colWidths=[1.5 * inch, 1.5 * inch, 2 * inch, 2 * inch])
        pay_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(pay_table)

    # Notes and payment terms
    if invoice.payment_terms:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"<b>Payment Terms:</b> {invoice.payment_terms}", normal_style))
    if invoice.notes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Notes:</b> {invoice.notes}", normal_style))

    doc.build(elements)
    return buffer.getvalue()
