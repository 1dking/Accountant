"""Pydantic schemas for credit notes and refunds."""


from typing import Optional

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.invoicing.credit_models import CreditNoteStatus


class CreditNoteCreate(BaseModel):
    amount: float = Field(gt=0)
    reason: str | None = None
    issue_date: date


class CreditNoteResponse(BaseModel):
    id: uuid.UUID
    credit_note_number: str
    invoice_id: uuid.UUID
    contact_id: uuid.UUID
    amount: float
    reason: str | None
    status: CreditNoteStatus
    issue_date: date
    applied_at: Optional[datetime]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreditNoteListItem(BaseModel):
    id: uuid.UUID
    credit_note_number: str
    invoice_id: uuid.UUID
    contact_id: uuid.UUID
    amount: float
    reason: str | None
    status: CreditNoteStatus
    issue_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactCreditBalance(BaseModel):
    contact_id: uuid.UUID
    total_issued: float
    total_applied: float
    available_balance: float
