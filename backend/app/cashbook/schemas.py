"""Pydantic schemas for the cashbook module."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.cashbook.models import AccountType, CategoryType, EntryStatus, EntryType


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
    currency: str = "CAD"
    opening_balance: Decimal = Decimal("0.0")
    opening_balance_date: date
    default_tax_rate_id: str | None = None


class PaymentAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    account_type: AccountType | None = None
    currency: str | None = None
    opening_balance: Decimal | None = None
    opening_balance_date: Optional[date] = None
    default_tax_rate_id: str | None = None
    is_active: bool | None = None


class PaymentAccountResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: AccountType
    currency: str
    opening_balance: Decimal
    opening_balance_date: date
    default_tax_rate_id: str | None
    is_active: bool
    current_balance: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountDeleteRequest(BaseModel):
    """Request body for deleting an account that may have entries."""
    action: str = Field(pattern=r"^(move|delete)$")
    target_account_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Cashbook Entry schemas
# ---------------------------------------------------------------------------


class CashbookEntryCreate(BaseModel):
    account_id: uuid.UUID
    entry_type: EntryType
    date: date
    description: str = Field(min_length=1, max_length=500)
    total_amount: Decimal = Field(gt=Decimal(0))
    tax_amount: Decimal | None = None
    tax_override: bool = False
    category_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None
    source: str | None = None
    source_id: str | None = None


class CashbookEntryUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    entry_type: EntryType | None = None
    date: Optional[date] = None
    description: str | None = Field(None, min_length=1, max_length=500)
    total_amount: Decimal | None = Field(None, gt=Decimal(0))
    tax_amount: Decimal | None = None
    tax_override: bool | None = None
    category_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None
    status: EntryStatus | None = None


class CashbookEntryResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    entry_type: EntryType
    date: date
    description: str
    total_amount: Decimal
    tax_amount: Decimal | None
    tax_rate_used: Decimal | None
    tax_override: bool
    category_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    document_id: uuid.UUID | None
    source: str | None
    source_id: str | None
    notes: str | None
    user_id: uuid.UUID
    status: EntryStatus = EntryStatus.PENDING
    is_deleted: bool = False
    split_parent_id: uuid.UUID | None = None
    bank_balance: Decimal | None = None
    category: TransactionCategoryResponse | None = None
    account_name: str | None = None
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
    status: EntryStatus | None = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    search: str | None = None
    include_deleted: bool = False


class CategoryTotal(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    category_type: CategoryType | None
    entry_type: EntryType
    total_amount: Decimal
    total_tax: Decimal
    count: int


class CashbookSummary(BaseModel):
    opening_balance: Decimal
    closing_balance: Decimal
    total_income: Decimal
    total_expenses: Decimal
    net_change: Decimal
    total_tax_collected: Decimal
    total_tax_paid: Decimal
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
    total_amount: Decimal
    category_name: str | None
    entry_type: EntryType
    tax_amount: Decimal | None
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


# ---------------------------------------------------------------------------
# Capture (upload-and-book) schemas
# ---------------------------------------------------------------------------


class CashbookCaptureResponse(BaseModel):
    document_id: uuid.UUID
    document_title: str
    entry_id: uuid.UUID | None = None
    entry_type: EntryType | None = None
    entry_amount: Decimal | None = None
    entry_description: str | None = None
    entry_date: str | None = None
    category_name: str | None = None
    extraction: dict | None = None
    processing_time_ms: int


# ---------------------------------------------------------------------------
# Bulk action schemas
# ---------------------------------------------------------------------------


class BulkDeleteRequest(BaseModel):
    entry_ids: list[uuid.UUID]


class BulkCategorizeRequest(BaseModel):
    entry_ids: list[uuid.UUID]
    category_id: uuid.UUID


class BulkMoveAccountRequest(BaseModel):
    entry_ids: list[uuid.UUID]
    account_id: uuid.UUID


class BulkStatusRequest(BaseModel):
    entry_ids: list[uuid.UUID]
    status: EntryStatus


# ---------------------------------------------------------------------------
# Split transaction schemas
# ---------------------------------------------------------------------------


class SplitLineItem(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=Decimal(0))
    category_id: uuid.UUID | None = None
    notes: str | None = None


class SplitTransactionRequest(BaseModel):
    lines: list[SplitLineItem] = Field(min_length=2)
