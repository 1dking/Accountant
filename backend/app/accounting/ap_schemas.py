"""Pydantic schemas for Accounts Payable / vendor bills."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.accounting.ledger_models import BillStatus


class VendorBillLineInput(BaseModel):
    account_id: uuid.UUID
    description: str | None = Field(default=None, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class VendorBillCreate(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=255)
    vendor_contact_id: uuid.UUID | None = None
    bill_number: str | None = Field(default=None, max_length=50)
    bill_date: date
    due_date: date | None = None
    memo: str | None = None
    #: DRAFT or PENDING at creation; posting statuses are reached via workflow.
    status: str | None = None
    lines: list[VendorBillLineInput] = Field(min_length=1)


class VendorBillUpdate(BaseModel):
    vendor_name: str | None = Field(default=None, max_length=255)
    vendor_contact_id: uuid.UUID | None = None
    bill_date: date | None = None
    due_date: date | None = None
    memo: str | None = None
    status: str | None = None
    lines: list[VendorBillLineInput] | None = None


class VendorBillPay(BaseModel):
    cash_account_id: uuid.UUID
    payment_date: date


class VendorBillLineResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_code: str | None = None
    account_name: str | None = None
    description: str | None
    amount: Decimal

    model_config = {"from_attributes": True}


class VendorBillResponse(BaseModel):
    id: uuid.UUID
    bill_number: str
    vendor_name: str
    vendor_contact_id: uuid.UUID | None
    bill_date: date
    due_date: date | None
    memo: str | None
    total_amount: Decimal
    status: BillStatus
    approval_journal_id: uuid.UUID | None
    payment_journal_id: uuid.UUID | None
    scheduled_payment_date: date | None
    paid_at: datetime | None
    created_at: datetime
    lines: list[VendorBillLineResponse]

    model_config = {"from_attributes": True}
