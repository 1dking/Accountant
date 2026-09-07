"""Pydantic shapes for the joint filing package."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class T2125LineOut(BaseModel):
    line: str
    label: str
    part: str
    amount: Decimal
    #: After deductibility rules (meals 50%). Equals amount for most lines.
    allowable: Decimal
    #: Source rows that rolled into this line (code · name · amount).
    sources: list[dict] = Field(default_factory=list)
    computed: bool = False


class T2125Statement(BaseModel):
    year: int
    period_start: date
    period_end: date
    fiscal_year_end_month: int
    gross_sales: Decimal          # 8000
    other_income: Decimal         # 8230
    gross_income: Decimal         # 8299
    cost_of_goods_sold: Decimal   # 8518
    gross_profit: Decimal         # 8519
    lines: list[T2125LineOut]
    total_expenses: Decimal       # 9368 (allowable)
    net_income: Decimal           # 9369 → T1 line 13500
    excluded_non_deductible: list[dict] = Field(default_factory=list)
    unmapped: list[dict] = Field(default_factory=list)
    gst_hst: dict | None = None   # GST34 lines for the same period


class T1LineOut(BaseModel):
    line: str
    label: str
    amount: Decimal
    transaction_count: int


class T1PersonalSummary(BaseModel):
    year: int
    total_in: Decimal
    total_out: Decimal
    net_business_income_line_13500: Decimal
    lines: list[T1LineOut]
    #: Personal-ledger transactions with no T1 category — informational.
    uncategorized_out: Decimal


class ReadinessItem(BaseModel):
    key: str
    status: str            # "ok" | "warn" | "todo" | "info"
    label: str
    detail: str | None = None
    action_path: str | None = None


class FilingPackage(BaseModel):
    year: int
    business_name: str | None
    province: str | None
    business_number: str | None
    gst_hst_number: str | None
    generated_at: date
    personal_included: bool
    t2125: T2125Statement
    t1: T1PersonalSummary | None
    readiness: list[ReadinessItem]
