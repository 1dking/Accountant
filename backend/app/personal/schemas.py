"""Pydantic schemas for the personal ledger."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PersonalAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    account_type: str = Field("bank", max_length=30)
    currency: str = Field("CAD", min_length=3, max_length=3)
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: date


class PersonalAccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    account_type: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class PersonalAccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    account_type: str
    currency: str
    opening_balance: Decimal
    opening_balance_date: date
    is_active: bool
    current_balance: Decimal | None = None

    model_config = {"from_attributes": True}


class PersonalTransactionCreate(BaseModel):
    account_id: uuid.UUID
    date: date
    direction: Literal["in", "out"]
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=1, max_length=500)
    category_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=1000)


class PersonalTransactionUpdate(BaseModel):
    date: Optional[date] = None
    direction: Optional[Literal["in", "out"]] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    category_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=1000)


class PersonalTransactionResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    date: date
    direction: str
    amount: Decimal
    description: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class PersonalCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    direction: str

    model_config = {"from_attributes": True}


class CategoryCashflow(BaseModel):
    category_id: uuid.UUID | None = None
    category_name: str
    direction: str
    total: Decimal
    count: int


class PersonalCashflowSummary(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    total_in: Decimal
    total_out: Decimal
    net: Decimal
    by_category: list[CategoryCashflow]
