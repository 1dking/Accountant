
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.budgets.models import PeriodType


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=Decimal(0))
    period_type: PeriodType
    year: int = Field(ge=2020, le=2100)
    month: int | None = Field(None, ge=1, le=12)


class BudgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    amount: Decimal | None = Field(None, gt=Decimal(0))


class BudgetResponse(BaseModel):
    id: uuid.UUID
    name: str
    category_id: uuid.UUID | None
    amount: Decimal
    period_type: PeriodType
    year: int
    month: int | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetVsActual(BaseModel):
    budget_id: uuid.UUID
    budget_name: str
    category_id: uuid.UUID | None
    category_name: str
    budgeted_amount: Decimal
    actual_amount: Decimal
    remaining: Decimal
    percentage_used: Decimal
