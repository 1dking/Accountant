
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.income.models import IncomeCategory


class IncomeCreate(BaseModel):
    contact_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    category: IncomeCategory = IncomeCategory.OTHER
    description: str = Field(min_length=1, max_length=1000)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=3)
    date: date
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=255)
    notes: str | None = None


class IncomeUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    category: IncomeCategory | None = None
    description: str | None = Field(None, min_length=1, max_length=1000)
    amount: float | None = Field(None, gt=0)
    currency: str | None = Field(None, max_length=3)
    date: date | None = None
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=255)
    notes: str | None = None


class IncomeResponse(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    category: IncomeCategory
    description: str
    amount: float
    currency: str
    date: date
    payment_method: str | None
    reference: str | None
    notes: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncomeListItem(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    category: IncomeCategory
    description: str
    amount: float
    currency: str
    date: date
    payment_method: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncomeFilter(BaseModel):
    search: str | None = None
    category: IncomeCategory | None = None
    contact_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class IncomeCategorySummary(BaseModel):
    category: str
    total: float
    count: int


class IncomeMonthSummary(BaseModel):
    year: int
    month: int
    total: float
    count: int


class IncomeSummary(BaseModel):
    total_amount: float
    income_count: int
    by_category: list[IncomeCategorySummary]
    by_month: list[IncomeMonthSummary]
