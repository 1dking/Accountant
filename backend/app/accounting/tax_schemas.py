"""Pydantic schemas for sales tax tracking."""

from datetime import date, datetime
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
    # Canadian tax matrix — optional on user-created rates.
    tax_type: Optional[str] = Field(None, pattern="^(gst|hst|pst|rst|qst|other)$")
    province: Optional[str] = Field(None, min_length=2, max_length=2)
    is_recoverable: bool = True
    effective_from: Optional[date] = None


class TaxRateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    rate: Optional[float] = Field(None, ge=0, le=100)
    description: Optional[str] = Field(None, max_length=500)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    region: Optional[str] = Field(None, max_length=100)
    tax_type: Optional[str] = Field(None, pattern="^(gst|hst|pst|rst|qst|other)$")
    province: Optional[str] = Field(None, min_length=2, max_length=2)
    is_recoverable: Optional[bool] = None
    effective_from: Optional[date] = None


class TaxRateResponse(BaseModel):
    id: str
    name: str
    rate: float
    description: Optional[str]
    is_default: bool
    is_active: bool
    region: Optional[str]
    tax_type: Optional[str] = None
    province: Optional[str] = None
    is_recoverable: bool = True
    is_system: bool = False
    effective_from: Optional[date] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Province matrix
# ---------------------------------------------------------------------------


class ProvinceInfo(BaseModel):
    code: str
    name: str
    #: Human summary of the regime — "HST 13%", "GST 5% + PST 7%".
    regime: str
    combined_rate: float


class ProvinceRatesResponse(BaseModel):
    province: str
    primary: Optional[TaxRateResponse]
    secondary: Optional[TaxRateResponse]
    combined_rate: float


# ---------------------------------------------------------------------------
# Tax Liability Report schemas
# ---------------------------------------------------------------------------


class TaxLiabilityReport(BaseModel):
    date_from: str
    date_to: str
    total_tax_collected: float
    total_tax_paid: float
    net_tax_liability: float
