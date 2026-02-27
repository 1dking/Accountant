"""Pydantic schemas for the accounting module."""


import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.accounting.models import ApprovalStatusEnum, ExpenseStatus, PaymentMethod

# ---------------------------------------------------------------------------
# Expense Category schemas
# ---------------------------------------------------------------------------


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=50)


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=50)


class ExpenseCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    icon: str | None
    is_system: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Expense Line Item schemas
# ---------------------------------------------------------------------------


class ExpenseLineItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float | None = None
    unit_price: float | None = None
    total: float


class ExpenseLineItemResponse(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    description: str
    quantity: float | None
    unit_price: float | None
    total: float

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Expense schemas
# ---------------------------------------------------------------------------


class ExpenseCreate(BaseModel):
    vendor_name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=3)
    tax_amount: float | None = None
    date: date
    payment_method: PaymentMethod | None = None
    category_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None
    is_recurring: bool = False
    line_items: list[ExpenseLineItemCreate] = Field(default_factory=list)


class ExpenseUpdate(BaseModel):
    vendor_name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)
    amount: float | None = Field(None, gt=0)
    currency: str | None = Field(None, max_length=3)
    tax_amount: float | None = None
    date: date | None = None
    payment_method: PaymentMethod | None = None
    status: ExpenseStatus | None = None
    category_id: uuid.UUID | None = None
    notes: str | None = None
    is_recurring: bool | None = None
    line_items: list[ExpenseLineItemCreate] | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    category_id: uuid.UUID | None
    user_id: uuid.UUID
    vendor_name: str | None
    description: str | None
    amount: float
    currency: str
    tax_amount: float | None
    date: date
    payment_method: PaymentMethod | None
    status: ExpenseStatus
    notes: str | None
    is_recurring: bool
    ai_category_suggestion: str | None
    ai_confidence: float | None
    category: ExpenseCategoryResponse | None = None
    line_items: list[ExpenseLineItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExpenseListItem(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    category_id: uuid.UUID | None
    user_id: uuid.UUID
    vendor_name: str | None
    description: str | None
    amount: float
    currency: str
    date: date
    payment_method: PaymentMethod | None
    status: ExpenseStatus
    is_recurring: bool
    category: ExpenseCategoryResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Filter / Summary schemas
# ---------------------------------------------------------------------------


class ExpenseFilter(BaseModel):
    search: str | None = None
    category_id: uuid.UUID | None = None
    status: ExpenseStatus | None = None
    payment_method: PaymentMethod | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    user_id: uuid.UUID | None = None


class CategorySpend(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    category_color: str | None
    total: float
    count: int


class MonthlySpend(BaseModel):
    year: int
    month: int
    total: float
    count: int


class VendorSpend(BaseModel):
    vendor_name: str
    total: float
    count: int


class ExpenseSummary(BaseModel):
    total_amount: float
    expense_count: int
    average_amount: float
    by_category: list[CategorySpend]
    by_month: list[MonthlySpend]
    top_vendors: list[VendorSpend]


# ---------------------------------------------------------------------------
# Expense Approval schemas
# ---------------------------------------------------------------------------


class ExpenseApprovalRequest(BaseModel):
    assigned_to: uuid.UUID


class ExpenseApprovalResolve(BaseModel):
    comment: str | None = None


class ExpenseApprovalResponse(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    requested_by: uuid.UUID
    assigned_to: uuid.UUID
    status: ApprovalStatusEnum
    comment: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
