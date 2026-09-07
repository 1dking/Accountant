"""Pay-stub and T4 PDFs. ReportLab platypus, same palette as invoicing/pdf.py.

The T4 here is the employee copy laid out as a clear box-by-box statement —
not the CRA-prescribed print form (which needs CRA-approved layout for the
paper-filing copy). For e-filing, the XML/Internet-file-transfer path is the
real submission; this PDF is what the employee keeps.
"""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.payroll.models import Employee, PayrollRun, PayStub
from app.payroll.schemas import EmployeeYTD

_INK = colors.HexColor("#1e3a5f")
_HEAD_BG = colors.HexColor("#f1f5f9")
_HEAD_FG = colors.HexColor("#334155")
_GRID = colors.HexColor("#e2e8f0")


def _m(v) -> str:
    return f"${Decimal(str(v or 0)):,.2f}"


def _doc(buffer: io.BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )


def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("PTitle", parent=s["Title"], fontSize=20, textColor=_INK, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("PSub", parent=s["Normal"], fontSize=9, textColor=colors.grey),
        "normal": s["Normal"],
        "small": ParagraphStyle("PSmall", parent=s["Normal"], fontSize=8, textColor=colors.HexColor("#64748b")),
        "h": ParagraphStyle("PH", parent=s["Normal"], fontSize=10, textColor=_HEAD_FG, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3),
    }


def _header(elements, st, *, title: str, company, logo_bytes: bytes | None, right_lines: list[str]):
    if logo_bytes:
        img = Image(io.BytesIO(logo_bytes), width=1.5 * inch, height=0.75 * inch)
        img.hAlign = "LEFT"
        elements.append(img)
        elements.append(Spacer(1, 6))
    name = (company.company_name if company and company.company_name else "Employer")
    left = [Paragraph(name, st["title"])]
    if company:
        addr = ", ".join(filter(None, [
            company.address_line1,
            ", ".join(filter(None, [company.city, company.province or company.state])) + (f" {company.zip_code}" if company.zip_code else ""),
        ]))
        if addr.strip(", "):
            left.append(Paragraph(addr, st["sub"]))
        if company.business_number:
            left.append(Paragraph(f"Business Number {company.business_number}", st["sub"]))
    right = [Paragraph(f"<b>{title}</b>", ParagraphStyle("R", parent=st["normal"], alignment=2, fontSize=12))]
    right += [Paragraph(l, ParagraphStyle("RS", parent=st["sub"], alignment=2)) for l in right_lines]
    t = Table([[left, right]], colWidths=[4.25 * inch, 2.75 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(t)
    elements.append(Spacer(1, 14))


def _kv_table(rows: list[tuple[str, str]], *, widths=(2.0 * inch, 1.4 * inch), bold_last=False) -> Table:
    t = Table([[k, v] for k, v in rows], colWidths=list(widths))
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, _GRID),
    ]
    if bold_last:
        style += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 1, _HEAD_FG)]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Pay stub
# ---------------------------------------------------------------------------


def generate_stub_pdf(stub: PayStub, run: PayrollRun, emp: Employee, company, logo_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    doc = _doc(buf)
    st = _styles()
    el: list = []
    qc = stub.province_of_employment == "QC"

    _header(el, st, title="Statement of Earnings", company=company, logo_bytes=logo_bytes, right_lines=[
        f"Pay period {run.period_start.isoformat()} to {run.period_end.isoformat()}",
        f"Pay date {run.pay_date.isoformat()}",
        f"{run.pay_frequency.value.title()} · Tax tables {stub.tables_version}",
    ])

    # Employee block
    emp_lines = [f"<b>{emp.full_name}</b>"]
    if emp.job_title:
        emp_lines.append(emp.job_title)
    addr = ", ".join(filter(None, [emp.address_line1, emp.city, emp.province, emp.postal_code]))
    if addr:
        emp_lines.append(addr)
    emp_lines.append(f"Province of employment: {stub.province_of_employment}")
    el.append(Paragraph("<br/>".join(emp_lines), st["normal"]))
    el.append(Spacer(1, 12))

    # Earnings / deductions side by side
    earn: list[tuple[str, str]] = []
    if stub.hours is not None:
        earn.append((f"Regular ({Decimal(stub.hours):g} h × {_m(stub.rate)})", _m(stub.regular_pay)))
    else:
        earn.append(("Regular (salary)", _m(stub.regular_pay)))
    for label, v in (("Overtime", stub.overtime_pay), ("Bonus", stub.bonus), ("Vacation pay", stub.vacation_pay), ("Other earnings", stub.other_earnings)):
        if v:
            earn.append((label, _m(v)))
    earn.append(("Gross pay", _m(stub.gross)))

    ded: list[tuple[str, str]] = [
        ("QPP" if qc else "CPP", _m(stub.cpp_employee)),
    ]
    if stub.cpp2_employee:
        ded.append(("QPP2" if qc else "CPP2", _m(stub.cpp2_employee)))
    ded.append(("EI", _m(stub.ei_employee)))
    if qc:
        ded.append(("QPIP", _m(stub.qpip_employee)))
    ded += [("Federal income tax", _m(stub.federal_tax)), (f"{stub.province_of_employment} income tax", _m(stub.provincial_tax))]
    if stub.other_deductions:
        ded.append(("Other deductions", _m(stub.other_deductions)))
    total_ded = (stub.cpp_employee + stub.cpp2_employee + stub.ei_employee + stub.qpip_employee
                 + stub.federal_tax + stub.provincial_tax + stub.other_deductions)
    ded.append(("Total deductions", _m(total_ded)))

    side = Table(
        [[Paragraph("Earnings", st["h"]), Paragraph("Deductions", st["h"])],
         [_kv_table(earn, bold_last=True), _kv_table(ded, bold_last=True)]],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(side)
    el.append(Spacer(1, 10))

    net = Table([["NET PAY", _m(stub.net_pay)]], colWidths=[5.6 * inch, 1.4 * inch])
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _HEAD_BG), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    el.append(net)
    el.append(Spacer(1, 16))

    # Employer contributions + YTD
    er = [("CPP/QPP (employer)", _m(stub.cpp_employer + stub.cpp2_employer)), ("EI (employer)", _m(stub.ei_employer))]
    if qc:
        er.append(("QPIP (employer)", _m(stub.qpip_employer)))
    ytd = [
        ("Gross", _m(stub.ytd_gross)), ("CPP/QPP", _m(stub.ytd_cpp_employee + stub.ytd_cpp2_employee)),
        ("EI", _m(stub.ytd_ei_employee)),
    ]
    if qc:
        ytd.append(("QPIP", _m(stub.ytd_qpip_employee)))
    ytd += [("Federal tax", _m(stub.ytd_federal_tax)), ("Provincial tax", _m(stub.ytd_provincial_tax)), ("Net pay", _m(stub.ytd_net))]
    bottom = Table(
        [[Paragraph("Employer contributions", st["h"]), Paragraph(f"Year to date ({run.pay_date.year})", st["h"])],
         [_kv_table(er), _kv_table(ytd, bold_last=True)]],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(bottom)
    el.append(Spacer(1, 12))
    el.append(Paragraph(
        f"Insurable earnings {_m(stub.insurable_earnings)} · Insurable hours {Decimal(stub.insurable_hours):g} · "
        f"Pensionable earnings {_m(stub.pensionable_earnings)}", st["small"]))
    if emp.vacation_accrued_balance and not emp.vacation_pay_each_period:
        el.append(Paragraph(f"Vacation pay accrued (unpaid): {_m(emp.vacation_accrued_balance)}", st["small"]))

    doc.build(el)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# T4 — Statement of Remuneration Paid (employee copy)
# ---------------------------------------------------------------------------


def generate_t4_pdf(emp: Employee, ytd: EmployeeYTD, year: int, company, logo_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    doc = _doc(buf)
    st = _styles()
    el: list = []
    qc = emp.province_of_employment == "QC"

    _header(el, st, title=f"T4 — Statement of Remuneration Paid — {year}", company=company, logo_bytes=logo_bytes, right_lines=[
        "Employee copy", f"Issued {date.today().isoformat()}",
    ])

    sin = emp.sin or ""
    sin_fmt = f"{sin[0:3]} {sin[3:6]} {sin[6:9]}" if len(sin) == 9 else "— not on file —"
    addr = ", ".join(filter(None, [emp.address_line1, emp.address_line2, emp.city, emp.province, emp.postal_code]))
    who = Table([
        [Paragraph("<b>Employee's name and address</b>", st["small"]), Paragraph("<b>Box 12 — Social insurance number</b>", st["small"]), Paragraph("<b>Box 10 — Province of employment</b>", st["small"])],
        [Paragraph(f"{emp.full_name}<br/>{addr}", st["normal"]), Paragraph(sin_fmt, st["normal"]), Paragraph(emp.province_of_employment, st["normal"])],
    ], colWidths=[3.5 * inch, 2.0 * inch, 1.5 * inch])
    who.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el.append(who)
    el.append(Spacer(1, 12))

    boxes: list[tuple[str, str, str]] = [
        ("14", "Employment income", _m(ytd.gross)),
        ("16", "Employee's CPP contributions", _m(Decimal("0") if qc else ytd.cpp_employee)),
        ("16A", "Employee's second CPP contributions", _m(Decimal("0") if qc else ytd.cpp2_employee)),
        ("17", "Employee's QPP contributions", _m(ytd.cpp_employee if qc else Decimal("0"))),
        ("17A", "Employee's second QPP contributions", _m(ytd.cpp2_employee if qc else Decimal("0"))),
        ("18", "Employee's EI premiums", _m(ytd.ei_employee)),
        ("22", "Income tax deducted", _m(ytd.federal_tax + ytd.provincial_tax)),
        ("24", "EI insurable earnings", _m(ytd.insurable_earnings)),
        ("26", "CPP/QPP pensionable earnings", _m(ytd.pensionable_earnings)),
        ("44", "Union dues", _m(0)),
        ("46", "Charitable donations", _m(0)),
        ("52", "Pension adjustment", _m(0)),
        ("55", "Employee's PPIP premiums", _m(ytd.qpip_employee)),
        ("56", "PPIP insurable earnings", _m(ytd.insurable_earnings if qc else Decimal("0"))),
    ]
    rows = [["Box", "Description", "Amount"]] + [[b, d, a] for b, d, a in boxes]
    t = Table(rows, colWidths=[0.7 * inch, 4.6 * inch, 1.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEAD_BG), ("TEXTCOLOR", (0, 0), (-1, 0), _HEAD_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(t)
    el.append(Spacer(1, 12))
    el.append(Paragraph(
        f"Employer's account number: {company.business_number + 'RP0001' if company and company.business_number else '— not on file —'} · "
        f"{ytd.stub_count} pay periods · Employee copy — keep for your records. "
        "Box 22 combines federal and provincial tax; Quebec provincial tax is reported on the Relevé 1.",
        st["small"],
    ))

    doc.build(el)
    return buf.getvalue()
