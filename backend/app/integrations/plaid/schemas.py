
from typing import Optional

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
    last_sync_at: Optional[datetime] = None
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
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    page_size: int = 50


class CategorizeTransactionRequest(BaseModel):
    as_type: str  # "expense" | "income" | "ignore"
    expense_category_id: uuid.UUID | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Categorization Rules
# ---------------------------------------------------------------------------


class CategorizationRuleCreate(BaseModel):
    name: str
    match_field: str  # "name" | "merchant_name" | "category"
    match_type: str  # "contains" | "exact" | "starts_with" | "regex"
    match_value: str
    assign_category_id: uuid.UUID
    priority: int = 0
    is_active: bool = True


class CategorizationRuleUpdate(BaseModel):
    name: Optional[str] = None
    match_field: Optional[str] = None
    match_type: Optional[str] = None
    match_value: Optional[str] = None
    assign_category_id: Optional[uuid.UUID] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class CategorizationRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    match_field: str
    match_type: str
    match_value: str
    assign_category_id: uuid.UUID
    priority: int
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
