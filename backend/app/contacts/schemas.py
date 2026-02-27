from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.contacts.models import ContactType


class ContactCreate(BaseModel):
    type: ContactType
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=20)
    country: str = Field(default="US", max_length=100)
    tax_id: str | None = Field(None, max_length=50)
    notes: str | None = None


class ContactUpdate(BaseModel):
    type: ContactType | None = None
    company_name: str | None = Field(None, min_length=1, max_length=255)
    contact_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    tax_id: str | None = Field(None, max_length=50)
    notes: str | None = None
    is_active: bool | None = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    type: ContactType
    company_name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    country: str
    tax_id: str | None
    notes: str | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactListItem(BaseModel):
    id: uuid.UUID
    type: ContactType
    company_name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    city: str | None
    state: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactFilter(BaseModel):
    search: str | None = None
    type: ContactType | None = None
    is_active: bool | None = None
