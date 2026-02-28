"""Pydantic schemas for the cashbook module."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.cashbook.models import AccountType, CategoryType, EntryType


# ---------------------------------------------------------------------------
# Transaction Category schemas
# ---------------------------------------------------------------------------


class TransactionCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category_type: CategoryType
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=50)


class TransactionCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    category_type: CategoryType | None = None
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=50)


class TransactionCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    category_type: CategoryType
    color: str | None
    icon: str | None
    is_system: bool
    display_order: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Payment Account schemas
# ---------------------------------------------------------------------------


class PaymentAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    account_type: AccountType
    opening_balance: float = 0.0
    opening_balance_date: date
    default_tax_rate_id: str | None = None


class PaymentAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    account_type: AccountType | None = None
    opening_balance: float | None = None
    opening_balance_date: Optional[date] = None
    default_tax_rate_id: str | None = None
    is_active: bool | None = None


class PaymentAccountResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: AccountType
    opening_balance: float
    opening_balance_date: date
    default_tax_rate_id: str | None
    is_active: bool
    current_balance: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cashbook Entry schemas
# ---------------------------------------------------------------------------


class CashbookEntryCreate(BaseModel):
    account_id: uuid.UUID
    entry_type: EntryType
    date: date
    description: str = Field(min_length=1, max_length=500)
    total_amount: float = Field(gt=0)
    tax_amount: float | None = None
    tax_override: bool = False
    category_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None


class CashbookEntryUpdate(BaseModel):
    entry_type: EntryType | None = None
    date: Optional[date] = None
    description: str | None = Field(None, min_length=1, max_length=500)
    total_amount: float | None = Field(None, gt=0)
    tax_amount: float | None = None
    tax_override: bool | None = None
    category_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None


class CashbookEntryResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    entry_type: EntryType
    date: date
    description: str
    total_amount: float
    tax_amount: float | None
    tax_rate_used: float | None
    tax_override: bool
    category_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    document_id: uuid.UUID | None
    source: str | None
    source_id: str | None
    notes: str | None
    user_id: uuid.UUID
    bank_balance: float | None = None
    category: TransactionCategoryResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Filter / Summary schemas
# ---------------------------------------------------------------------------


class CashbookEntryFilter(BaseModel):
    account_id: uuid.UUID | None = None
    entry_type: EntryType | None = None
    category_id: uuid.UUID | None = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    search: str | None = None


class CategoryTotal(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    category_type: CategoryType | None
    entry_type: EntryType
    total_amount: float
    total_tax: float
    count: int


class CashbookSummary(BaseModel):
    opening_balance: float
    closing_balance: float
    total_income: float
    total_expenses: float
    net_change: float
    total_tax_collected: float
    total_tax_paid: float
    category_totals: list[CategoryTotal]
    period_start: date
    period_end: date


# ---------------------------------------------------------------------------
# Excel Import schemas
# ---------------------------------------------------------------------------


class ParsedExcelRow(BaseModel):
    row_number: int
    sheet_name: str
    date: date | None
    description: str
    total_amount: float
    category_name: str | None
    entry_type: EntryType
    tax_amount: float | None
    errors: list[str] = Field(default_factory=list)


class ImportPreview(BaseModel):
    rows: list[ParsedExcelRow]
    total_rows: int
    valid_rows: int
    error_rows: int
    sheets_found: list[str]


class ImportConfirm(BaseModel):
    account_id: uuid.UUID
    rows: list[ParsedExcelRow]
