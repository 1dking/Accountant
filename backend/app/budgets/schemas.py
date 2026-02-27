
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.budgets.models import PeriodType


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    amount: float = Field(gt=0)
    period_type: PeriodType
    year: int = Field(ge=2020, le=2100)
    month: int | None = Field(None, ge=1, le=12)


class BudgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    amount: float | None = Field(None, gt=0)


class BudgetResponse(BaseModel):
    id: uuid.UUID
    name: str
    category_id: uuid.UUID | None
    amount: float
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
    budgeted_amount: float
    actual_amount: float
    remaining: float
    percentage_used: float
