"""Pydantic schemas for sales tax tracking."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# TaxRate CRUD schemas
# ---------------------------------------------------------------------------


class TaxRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rate: float = Field(ge=0, le=100)
    description: Optional[str] = Field(None, max_length=500)
    is_default: bool = False
    region: Optional[str] = Field(None, max_length=100)


class TaxRateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    rate: Optional[float] = Field(None, ge=0, le=100)
    description: Optional[str] = Field(None, max_length=500)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    region: Optional[str] = Field(None, max_length=100)


class TaxRateResponse(BaseModel):
    id: str
    name: str
    rate: float
    description: Optional[str]
    is_default: bool
    is_active: bool
    region: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tax Liability Report schemas
# ---------------------------------------------------------------------------


class TaxLiabilityReport(BaseModel):
    date_from: str
    date_to: str
    total_tax_collected: float
    total_tax_paid: float
    net_tax_liability: float
