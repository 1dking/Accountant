
from decimal import Decimal
from typing import Optional

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contacts.schemas import ContactResponse
from app.invoicing.models import InvoiceStatus


class InvoiceLineItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1.0"), gt=Decimal(0))
    unit_price: Decimal = Field(gt=Decimal(0))
    tax_rate: Decimal | None = None


class InvoiceLineItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal | None
    total: Decimal

    model_config = {"from_attributes": True}


class InvoicePaymentCreate(BaseModel):
    amount: Decimal = Field(gt=Decimal(0))
    date: date
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=255)
    notes: str | None = None


class InvoicePaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    date: date
    payment_method: str | None
    reference: str | None
    notes: str | None
    recorded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    contact_id: uuid.UUID
    issue_date: date
    due_date: date
    tax_rate: Decimal | None = None
    discount_amount: Decimal = Decimal("0.0")
    currency: str = Field(default="USD", max_length=3)
    notes: str | None = None
    payment_terms: str | None = Field(None, max_length=500)
    line_items: list[InvoiceLineItemCreate] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    status: InvoiceStatus | None = None
    tax_rate: Decimal | None = None
    discount_amount: Decimal | None = None
    currency: str | None = Field(None, max_length=3)
    notes: str | None = None
    payment_terms: str | None = Field(None, max_length=500)
    line_items: list[InvoiceLineItemCreate] | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    contact_id: uuid.UUID
    issue_date: date
    due_date: date
    status: InvoiceStatus
    subtotal: Decimal
    tax_rate: Decimal | None
    tax_amount: Decimal | None
    discount_amount: Decimal
    total: Decimal
    currency: str
    notes: str | None
    payment_terms: str | None
    created_by: uuid.UUID
    contact: ContactResponse | None = None
    line_items: list[InvoiceLineItemResponse] = []
    payments: list[InvoicePaymentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    invoice_number: str
    contact_id: uuid.UUID
    issue_date: date
    due_date: date
    status: InvoiceStatus
    total: Decimal
    currency: str
    contact: ContactResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceFilter(BaseModel):
    search: str | None = None
    status: InvoiceStatus | None = None
    contact_id: uuid.UUID | None = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class InvoiceDashboardStats(BaseModel):
    total_outstanding: Decimal
    total_overdue: Decimal
    total_paid_this_month: Decimal
    invoice_count: int
