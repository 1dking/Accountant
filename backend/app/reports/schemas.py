from __future__ import annotations

from datetime import date

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
