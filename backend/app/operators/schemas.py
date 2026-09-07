"""Pydantic shapes for the operator (agency) surface."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.operators.models import CrmStyle, DataEntryMode, OnboardingTemplate, SubAccountStatus


class SubAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    template: OnboardingTemplate = OnboardingTemplate.MARKETING_AGENCY
    data_entry_mode: DataEntryMode = DataEntryMode.DOER
    crm_style: CrmStyle = CrmStyle.FULL
    notes: str | None = None
    #: Optionally invite the client's first user right away.
    client_email: EmailStr | None = None
    client_name: str | None = Field(None, max_length=255)


class SubAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: SubAccountStatus | None = None
    data_entry_mode: DataEntryMode | None = None
    crm_style: CrmStyle | None = None
    notes: str | None = None
    brand_logo_url: str | None = Field(None, max_length=500)
    brand_primary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    brand_secondary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    brand_accent_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class FeatureSet(BaseModel):
    enabled: bool


class MemberInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    #: "admin" runs the client tenant; "team_member" is staff; "client" is read-mostly.
    role: str = Field("admin", pattern=r"^(admin|manager|team_member|accountant|client|viewer)$")
    password: str | None = Field(None, min_length=8)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class SubAccountOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: SubAccountStatus
    template: OnboardingTemplate
    data_entry_mode: DataEntryMode
    crm_style: CrmStyle
    notes: str | None
    brand_logo_url: str | None
    brand_primary_color: str | None
    #: feature_key -> enabled, for every module (absent rows resolve to True).
    features: dict[str, bool] = Field(default_factory=dict)
    books_enabled: bool = True
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateInfo(BaseModel):
    key: OnboardingTemplate
    label: str
    description: str
    denies: list[str]
