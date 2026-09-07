"""Filing package PDF — T2125 statement, T1 personal summary, readiness."""
from __future__ import annotations

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from app.filing.schemas import FilingPackage
from app.payroll.pdf import _GRID, _HEAD_BG, _HEAD_FG, _doc, _header, _kv_table, _m, _styles


def generate_filing_pdf(pkg: FilingPackage, company, logo_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    doc = _doc(buf)
    st = _styles()
    el: list = []
    t = pkg.t2125

    _header(el, st, title=f"Tax filing package — {pkg.year}", company=company, logo_bytes=logo_bytes, right_lines=[
        f"Fiscal period {t.period_start.isoformat()} to {t.period_end.isoformat()}",
        f"Generated {pkg.generated_at.isoformat()}",
        "Personal half included" if pkg.personal_included else "Business half only",
    ])

    # ── T2125 ──
    el.append(Paragraph("T2125 — Statement of Business or Professional Activities", st["h"]))
    el.append(Paragraph("Mapped from the chart of accounts. Amounts tie to the trial balance for the period.", st["small"]))
    el.append(Spacer(1, 6))

    top = [
        ("8000  Gross sales, commissions or fees", _m(t.gross_sales)),
        ("8230  Other income", _m(t.other_income)),
        ("8299  Gross income", _m(t.gross_income)),
        ("8518  Cost of goods sold", _m(t.cost_of_goods_sold)),
        ("8519  Gross profit", _m(t.gross_profit)),
    ]
    el.append(_kv_table(top, widths=(5.2 * inch, 1.8 * inch), bold_last=True))
    el.append(Spacer(1, 8))

    rows = [["Line", "Expense", "Books", "Allowable"]]
    for ln in t.lines:
        if ln.part != "4 expenses":
            continue
        if ln.computed:
            rows.append([ln.line, ln.label, "—", Paragraph("<i>accountant to compute</i>", st["small"])])
        else:
            rows.append([ln.line, ln.label, _m(ln.amount), _m(ln.allowable)])
    rows.append(["9368", "Total expenses", "", _m(t.total_expenses)])
    rows.append(["9369", "Net income (loss) before adjustments → T1 line 13500", "", _m(t.net_income)])
    tbl = Table(rows, colWidths=[0.6 * inch, 4.2 * inch, 1.1 * inch, 1.1 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEAD_BG), ("TEXTCOLOR", (0, 0), (-1, 0), _HEAD_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, _GRID),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), _HEAD_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(tbl)

    if t.excluded_non_deductible or t.unmapped:
        el.append(Spacer(1, 8))
        notes = []
        if t.excluded_non_deductible:
            notes.append("Excluded as non-deductible: " + "; ".join(f"{s['name']} {_m(s['amount'])}" for s in t.excluded_non_deductible))
        if t.unmapped:
            notes.append("Landed on 9270 Other (no specific line matched): " + "; ".join(f"{s['name']} {_m(s['amount'])}" for s in t.unmapped))
        for n in notes:
            el.append(Paragraph(n, st["small"]))

    if t.gst_hst and t.gst_hst.get("has_recorded_tax"):
        g = t.gst_hst
        el.append(Spacer(1, 10))
        el.append(Paragraph("GST34 for the same period", st["h"]))
        el.append(_kv_table([
            ("101  Sales and other revenue", _m(g["line_101_sales"])),
            ("105  GST/HST collected", _m(g["line_105_collected"])),
            ("108  Input tax credits", _m(g["line_108_itc"])),
            ("109  Net tax", _m(g["line_109_net_tax"])),
        ], widths=(5.2 * inch, 1.8 * inch), bold_last=True))

    # ── T1 ──
    if pkg.t1:
        p = pkg.t1
        el.append(PageBreak())
        el.append(Paragraph(f"T1 — Personal summary {p.year}", st["h"]))
        el.append(Paragraph("From your personal ledger. Only categories tied to a T1 line are listed; everything else is lifestyle spending and stays off the return.", st["small"]))
        el.append(Spacer(1, 6))
        kv = [("13500  Net business income (from T2125 line 9369)", _m(p.net_business_income_line_13500))]
        kv += [(f"{ln.line}  {ln.label}  ({ln.transaction_count} txn)", _m(ln.amount)) for ln in p.lines]
        if not p.lines:
            kv.append(("No T1-linked personal categories used this year", "—"))
        el.append(_kv_table(kv, widths=(5.2 * inch, 1.8 * inch)))
        el.append(Spacer(1, 6))
        el.append(Paragraph(
            f"Personal money in {_m(p.total_in)} · out {_m(p.total_out)} · uncategorized spending {_m(p.uncategorized_out)}",
            st["small"]))

    # ── Readiness ──
    el.append(Spacer(1, 14))
    el.append(Paragraph("Before you file", st["h"]))
    mark = {"ok": "✓", "warn": "!", "todo": "○", "info": "·"}
    rows = [[mark.get(i.status, "·"), Paragraph(f"<b>{i.label}</b>" + (f"<br/>{i.detail}" if i.detail else ""), st["normal"])] for i in pkg.readiness]
    rt = Table(rows, colWidths=[0.3 * inch, 6.7 * inch])
    rt.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, _GRID),
    ]))
    el.append(rt)

    doc.build(el)
    return buf.getvalue()
