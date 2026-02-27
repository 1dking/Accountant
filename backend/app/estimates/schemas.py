
from typing import Optional

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contacts.schemas import ContactResponse
from app.estimates.models import EstimateStatus


class EstimateLineItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(gt=0)
    tax_rate: float | None = None


class EstimateLineItemResponse(BaseModel):
    id: uuid.UUID
    estimate_id: uuid.UUID
    description: str
    quantity: float
    unit_price: float
    tax_rate: float | None
    total: float

    model_config = {"from_attributes": True}


class EstimateCreate(BaseModel):
    contact_id: uuid.UUID
    issue_date: date
    expiry_date: date
    tax_rate: float | None = None
    discount_amount: float = 0.0
    currency: str = Field(default="USD", max_length=3)
    notes: str | None = None
    line_items: list[EstimateLineItemCreate] = Field(min_length=1)


class EstimateUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: EstimateStatus | None = None
    tax_rate: float | None = None
    discount_amount: float | None = None
    currency: str | None = Field(None, max_length=3)
    notes: str | None = None
    line_items: list[EstimateLineItemCreate] | None = None


class EstimateResponse(BaseModel):
    id: uuid.UUID
    estimate_number: str
    contact_id: uuid.UUID
    issue_date: date
    expiry_date: date
    status: EstimateStatus
    subtotal: float
    tax_rate: float | None
    tax_amount: float | None
    discount_amount: float
    total: float
    currency: str
    notes: str | None
    converted_invoice_id: uuid.UUID | None
    created_by: uuid.UUID
    contact: ContactResponse | None = None
    line_items: list[EstimateLineItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EstimateListItem(BaseModel):
    id: uuid.UUID
    estimate_number: str
    contact_id: uuid.UUID
    issue_date: date
    expiry_date: date
    status: EstimateStatus
    total: float
    currency: str
    contact: ContactResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EstimateFilter(BaseModel):
    search: str | None = None
    status: EstimateStatus | None = None
    contact_id: uuid.UUID | None = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
