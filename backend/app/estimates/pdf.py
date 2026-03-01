"""PDF generation for estimates using ReportLab."""

import io
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.estimates.models import Estimate


def generate_estimate_pdf(
    estimate: Estimate,
    business_name: str = "Accountant",
    logo_bytes: Optional[bytes] = None,
) -> bytes:
    """Generate a PDF for an estimate."""
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
    title_style = ParagraphStyle(
        "EstTitle", parent=styles["Title"], fontSize=24,
        textColor=colors.HexColor("#1e3a5f"),
    )
    subtitle_style = ParagraphStyle(
        "EstSub", parent=styles["Normal"], fontSize=10, textColor=colors.grey,
    )
    normal_style = styles["Normal"]

    elements: list = []

    # Logo
    if logo_bytes:
        try:
            logo_stream = io.BytesIO(logo_bytes)
            logo_img = Image(logo_stream, width=1.5 * inch, height=0.75 * inch)
            logo_img.hAlign = "LEFT"
            elements.append(logo_img)
            elements.append(Spacer(1, 6))
        except Exception:
            pass

    # Header
    elements.append(Paragraph(business_name, title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Estimate #{estimate.estimate_number}", subtitle_style))
    elements.append(Spacer(1, 20))

    # Estimate details table
    contact = estimate.contact
    bill_to = contact.company_name if contact else "\u2014"
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
        [
            Paragraph("<b>Prepared For:</b>", normal_style),
            Paragraph("<b>Estimate Details:</b>", normal_style),
        ],
        [
            Paragraph(bill_to, normal_style),
            Paragraph(
                f"Date: {estimate.issue_date}<br/>"
                f"Valid Until: {estimate.expiry_date}<br/>"
                f"Status: {estimate.status.value.replace('_', ' ').title()}<br/>"
                f"Currency: {estimate.currency}",
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
    for li in estimate.line_items:
        table_data.append([
            li.description,
            f"{li.quantity:.2f}",
            f"${li.unit_price:,.2f}",
            f"${li.total:,.2f}",
        ])

    items_table = Table(
        table_data, colWidths=[3.5 * inch, 1 * inch, 1.25 * inch, 1.25 * inch],
    )
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
        ["Subtotal:", f"${estimate.subtotal:,.2f}"],
    ]
    if estimate.tax_amount:
        rate_str = f" ({estimate.tax_rate}%)" if estimate.tax_rate else ""
        totals_data.append([f"Tax{rate_str}:", f"${estimate.tax_amount:,.2f}"])
    if estimate.discount_amount:
        totals_data.append(["Discount:", f"-${estimate.discount_amount:,.2f}"])
    totals_data.append(["Total:", f"${estimate.total:,.2f}"])

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

    # Signature section (if signed)
    signed_by = getattr(estimate, "signed_by_name", None)
    signed_at = getattr(estimate, "signed_at", None)
    if signed_by and signed_at:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("<b>Accepted By</b>", normal_style))
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(f"{signed_by} &mdash; {signed_at}", normal_style)
        )

    # Notes
    if estimate.notes:
        elements.append(Spacer(1, 20))
        elements.append(
            Paragraph(f"<b>Notes:</b> {estimate.notes}", normal_style)
        )

    doc.build(elements)
    return buffer.getvalue()
