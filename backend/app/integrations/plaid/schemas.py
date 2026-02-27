from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CreateLinkTokenResponse(BaseModel):
    link_token: str


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_name: str
    institution_id: str


class PlaidConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_name: str
    institution_id: str
    is_active: bool
    last_sync_at: datetime | None = None
    accounts: list[dict] | None = None
    created_at: datetime


class PlaidTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plaid_connection_id: uuid.UUID
    plaid_transaction_id: str
    account_id: str
    amount: float
    date: date
    name: str
    merchant_name: str | None = None
    category: str | None = None
    pending: bool
    is_income: bool
    matched_expense_id: uuid.UUID | None = None
    matched_income_id: uuid.UUID | None = None
    matched_invoice_id: uuid.UUID | None = None
    is_categorized: bool
    created_at: datetime


class PlaidTransactionFilters(BaseModel):
    connection_id: uuid.UUID | None = None
    is_categorized: bool | None = None
    is_income: bool | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = 1
    page_size: int = 50


class CategorizeTransactionRequest(BaseModel):
    as_type: str  # "expense" | "income" | "ignore"
    expense_category_id: uuid.UUID | None = None
    description: str | None = None
