"""Pydantic schemas for the company settings module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Nested helper for the default tax rate
# ---------------------------------------------------------------------------


class TaxRateInfo(BaseModel):
    """Minimal tax-rate representation embedded in the settings response."""

    id: str
    name: str
    rate: float

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class CompanySettingsResponse(BaseModel):
    id: uuid.UUID
    company_name: str | None = None
    company_email: str | None = None
    company_phone: str | None = None
    company_website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    logo_storage_path: str | None = None
    default_tax_rate_id: str | None = None
    default_currency: str = "CAD"
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    default_tax_rate: TaxRateInfo | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Update schema (partial update -- all fields optional)
# ---------------------------------------------------------------------------


class CompanySettingsUpdate(BaseModel):
    company_name: str | None = Field(None, max_length=255)
    company_email: str | None = Field(None, max_length=255)
    company_phone: str | None = Field(None, max_length=50)
    company_website: str | None = Field(None, max_length=255)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    default_tax_rate_id: str | None = None
    default_currency: str | None = Field(None, min_length=3, max_length=3)
