"""Pydantic schemas for accounting period closing/locking."""


from typing import Optional

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.accounting.period_models import PeriodStatus


class PeriodClose(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    notes: str | None = None


class PeriodReopen(BaseModel):
    notes: str | None = None


class PeriodResponse(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    status: PeriodStatus
    closed_by: uuid.UUID | None
    closed_at: Optional[datetime]
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
