
from typing import Optional

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.recurring.models import Frequency, RecurringType


class RecurringRuleCreate(BaseModel):
    type: RecurringType
    name: str = Field(min_length=1, max_length=255)
    frequency: Frequency
    next_run_date: date
    end_date: Optional[date] = None
    template_data: dict


class RecurringRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    frequency: Frequency | None = None
    next_run_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool | None = None
    template_data: dict | None = None


class RecurringRuleResponse(BaseModel):
    id: uuid.UUID
    type: RecurringType
    name: str
    frequency: Frequency
    next_run_date: date
    end_date: Optional[date]
    is_active: bool
    template_data: dict
    last_run_date: Optional[date]
    run_count: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecurringRuleListItem(BaseModel):
    id: uuid.UUID
    type: RecurringType
    name: str
    frequency: Frequency
    next_run_date: date
    end_date: Optional[date]
    is_active: bool
    last_run_date: Optional[date]
    run_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
