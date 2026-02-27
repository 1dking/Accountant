
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contacts.schemas import ContactResponse
from app.invoicing.models import InvoiceStatus


class InvoiceLineItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(gt=0)
    tax_rate: float | None = None


class InvoiceLineItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    description: str
    quantity: float
    unit_price: float
    tax_rate: float | None
    total: float

    model_config = {"from_attributes": True}


class InvoicePaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    date: date
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=255)
    notes: str | None = None


class InvoicePaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
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
    tax_rate: float | None = None
    discount_amount: float = 0.0
    currency: str = Field(default="USD", max_length=3)
    notes: str | None = None
    payment_terms: str | None = Field(None, max_length=500)
    line_items: list[InvoiceLineItemCreate] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    status: InvoiceStatus | None = None
    tax_rate: float | None = None
    discount_amount: float | None = None
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
    subtotal: float
    tax_rate: float | None
    tax_amount: float | None
    discount_amount: float
    total: float
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
    total: float
    currency: str
    contact: ContactResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceFilter(BaseModel):
    search: str | None = None
    status: InvoiceStatus | None = None
    contact_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class InvoiceDashboardStats(BaseModel):
    total_outstanding: float
    total_overdue: float
    total_paid_this_month: float
    invoice_count: int
