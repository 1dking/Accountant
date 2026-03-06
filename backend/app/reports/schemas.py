
from datetime import date
from typing import Optional

from pydantic import BaseModel


class CategoryAmount(BaseModel):
    category: str
    amount: float


class ProfitLossReport(BaseModel):
    date_from: date
    date_to: date
    total_income: float
    total_expenses: float
    net_profit: float
    income_by_category: list[CategoryAmount]
    expenses_by_category: list[CategoryAmount]


class TaxSummary(BaseModel):
    year: int
    taxable_income: float
    deductible_expenses: float
    tax_collected: float
    net_taxable: float


class CashFlowPeriod(BaseModel):
    period_label: str
    income: float
    expenses: float
    net: float


class CashFlowReport(BaseModel):
    date_from: date
    date_to: date
    periods: list[CashFlowPeriod]


class AccountsSummary(BaseModel):
    total_receivable: float
    total_payable: float
    overdue_receivable: float
    net_position: float


class AgingBucketTotals(BaseModel):
    current: float
    days_1_30: float
    days_31_60: float
    days_61_90: float
    days_90_plus: float
    total: float


class AgingBucket(AgingBucketTotals):
    name: str


class AgingReport(BaseModel):
    as_of_date: date
    buckets: list[AgingBucket]
    grand_totals: AgingBucketTotals


class QuarterlyBreakdown(BaseModel):
    quarter: int
    quarter_label: str  # "Q1 (Jan-Mar)"
    income: float
    expenses: float
    net: float
    tax_collected: float
    estimated_tax: float
    deadline: str  # "April 15"
    is_overdue: bool


class QuarterlyTaxReport(BaseModel):
    year: int
    tax_rate: float
    quarters: list[QuarterlyBreakdown]
    annual_total_income: float
    annual_total_expenses: float
    annual_net: float
    annual_tax_collected: float
    annual_estimated_tax: float
    income_by_category: list[CategoryAmount]
    expenses_by_category: list[CategoryAmount]


class YearOverYearComparison(BaseModel):
    current_year: int
    previous_year: int
    current_income: float
    previous_income: float
    income_change_pct: Optional[float]
    current_expenses: float
    previous_expenses: float
    expenses_change_pct: Optional[float]
    current_net: float
    previous_net: float


class TaxDeadline(BaseModel):
    quarter: int
    quarter_label: str
    deadline_date: str
    description: str
    is_past: bool
    days_until: Optional[int]
