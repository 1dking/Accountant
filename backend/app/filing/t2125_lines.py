"""T2125 line map — where each chart-of-accounts posting lands on the CRA
Statement of Business or Professional Activities.

Resolution order for an expense posting:
  1. exact CoA code (the seeded chart in coa_service.DEFAULT_COA)
  2. keyword match on the account/category name
  3. fallback: 9270 Other expenses (reported, and flagged as unmapped)

Income: 4000–4899 → 8000 Gross sales; 4900 Other income → 8230.
COGS: 5000–5999 → 8300 Purchases (part of cost of goods sold).

Two lines have a deductibility rule the books don't apply:
  - 8523 Meals & entertainment: 50% allowable (ITA 67.1)
  - Corporate income tax / owner draws are NOT deductible — excluded.

Two lines the books cannot produce and must be flagged for the accountant:
  - 9936 Capital cost allowance (depreciation is a bookkeeping entry; CCA is
    a tax computation by class)
  - 9945 Business-use-of-home (needs square footage / % — not in the ledger)

Line numbers per CRA T2125 (2025/2026 form).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class T2125Line:
    line: str
    label: str
    part: str            # "3A income" | "3C cogs" | "4 expenses" | "info"
    allowable_pct: int = 100
    computed: bool = False   # True = the books can't produce it; flag only


LINES: dict[str, T2125Line] = {l.line: l for l in [
    # Part 3A — Business income
    T2125Line("8000", "Gross sales, commissions or fees", "3A income"),
    T2125Line("8230", "Other income", "3A income"),
    T2125Line("8290", "Reserves deducted last year", "3A income", computed=True),
    # Part 3C — Cost of goods sold
    T2125Line("8300", "Purchases during the year (net of returns)", "3C cogs"),
    T2125Line("8320", "Direct wage costs", "3C cogs"),
    T2125Line("8340", "Subcontracts", "3C cogs"),
    # Part 4 — Net income before adjustments (expenses)
    T2125Line("8521", "Advertising", "4 expenses"),
    T2125Line("8523", "Meals and entertainment", "4 expenses", allowable_pct=50),
    T2125Line("8590", "Bad debts", "4 expenses"),
    T2125Line("8690", "Insurance", "4 expenses"),
    T2125Line("8710", "Interest and bank charges", "4 expenses"),
    T2125Line("8760", "Business taxes, licences and memberships", "4 expenses"),
    T2125Line("8810", "Office expenses", "4 expenses"),
    T2125Line("8811", "Office stationery and supplies", "4 expenses"),
    T2125Line("8860", "Professional fees (legal, accounting)", "4 expenses"),
    T2125Line("8871", "Management and administration fees", "4 expenses"),
    T2125Line("8910", "Rent", "4 expenses"),
    T2125Line("8960", "Repairs and maintenance", "4 expenses"),
    T2125Line("9060", "Salaries, wages and benefits (incl. employer contributions)", "4 expenses"),
    T2125Line("9180", "Property taxes", "4 expenses"),
    T2125Line("9200", "Travel expenses", "4 expenses"),
    T2125Line("9220", "Utilities", "4 expenses"),
    T2125Line("9224", "Fuel costs (except motor vehicle)", "4 expenses"),
    T2125Line("9275", "Delivery, freight and express", "4 expenses"),
    T2125Line("9281", "Motor vehicle expenses (not including CCA)", "4 expenses"),
    T2125Line("9270", "Other expenses", "4 expenses"),
    T2125Line("9936", "Capital cost allowance (CCA)", "4 expenses", computed=True),
    T2125Line("9945", "Business-use-of-home expenses", "4 expenses", computed=True),
]}

#: Seeded CoA code → T2125 line. Codes from accounting/coa_service.DEFAULT_COA.
CODE_MAP: dict[str, str] = {
    "5000": "8300",   # Cost of Goods Sold
    "6000": "8521",   # Advertising & Marketing
    "6100": "8710",   # Bank & Merchant Fees
    "6200": "8523",   # Meals & Entertainment
    "6300": "8810",   # Office Supplies
    "6400": "8910",   # Rent
    "6500": "9200",   # Travel
    "6600": "9220",   # Utilities
    "6700": "9060",   # Wages & Salaries
    "6710": "9060",   # Employer Payroll Taxes
    "6900": "9270",   # Other Expenses
}

#: Name keywords → T2125 line, checked in order (first match wins). Lower-case.
#: Covers the cashbook DEFAULT_CATEGORIES and common tenant-created names.
KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("advertis", "marketing"), "8521"),
    (("meal", "entertain", "dining", "restaurant"), "8523"),
    (("bad debt",), "8590"),
    (("insurance",), "8690"),
    (("interest", "bank fee", "bank charge", "merchant fee", "credit card fee"), "8710"),
    (("dues", "subscription", "licen", "membership", "permit"), "8760"),
    (("office suppl", "stationery"), "8811"),
    (("office",), "8810"),
    (("professional", "legal", "accounting", "bookkeep", "consult"), "8860"),
    (("management fee", "admin fee"), "8871"),
    (("rent", "lease"), "8910"),
    (("repair", "maintenance"), "8960"),
    (("wage", "salar", "payroll", "employer"), "9060"),
    (("property tax",), "9180"),
    (("travel", "airfare", "hotel", "lodging"), "9200"),
    (("telephone", "phone", "internet", "utilit", "hydro", "electric", "gas bill", "water"), "9220"),
    (("vehicle fuel", "vehicle", "car ", "auto", "mileage", "parking"), "9281"),
    (("fuel",), "9224"),
    (("shipping", "freight", "delivery", "postage", "courier"), "9275"),
    (("inventory", "purchase", "cost of goods", "cogs", "materials"), "8300"),
    (("subcontract", "contractor"), "8340"),
    (("education", "training"), "8760"),
    (("depreciation", "amortiz"), "9936"),
]

#: Names that are NOT deductible on a T2125 and must be excluded from expenses.
NON_DEDUCTIBLE_KEYWORDS: tuple[str, ...] = (
    "corporate tax", "income tax", "owner's draw", "owner draw", "owner's contribution",
    "credit card payment", "loan payment", "principal", "transfer", "hst/gst paid", "gst paid",
    "hst paid", "sales tax payable",
)

FALLBACK_EXPENSE = "9270"


def resolve_expense_line(code: str | None, name: str) -> tuple[str, bool]:
    """(line, mapped_explicitly). False = fell to the 9270 catch-all."""
    if code and code in CODE_MAP:
        return CODE_MAP[code], True
    n = (name or "").lower()
    for keys, line in KEYWORD_MAP:
        if any(k in n for k in keys):
            return line, True
    return FALLBACK_EXPENSE, False


def is_non_deductible(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in NON_DEDUCTIBLE_KEYWORDS)


def resolve_income_line(code: str | None, name: str) -> str:
    if code == "4900" or "other income" in (name or "").lower():
        return "8230"
    return "8000"


def allowable(line: str, amount: Decimal) -> Decimal:
    pct = LINES[line].allowable_pct if line in LINES else 100
    return (amount * Decimal(pct) / Decimal(100)).quantize(Decimal("0.01"))
