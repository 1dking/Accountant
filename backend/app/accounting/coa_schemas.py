"""Pydantic schemas for the Chart of Accounts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.accounting.ledger_models import AccountType


class ChartAccountBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    description: str | None = Field(default=None, max_length=255)
    parent_id: uuid.UUID | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Account code cannot be blank.")
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Account name cannot be blank.")
        return v


class ChartAccountCreate(ChartAccountBase):
    pass


class ChartAccountUpdate(BaseModel):
    """All fields optional. account_type is intentionally immutable once postings
    may exist — changing an account's type would silently flip its normal balance
    and corrupt the trial balance."""

    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None


class ChartAccountResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    account_type: AccountType
    normal_balance: str
    description: str | None
    parent_id: uuid.UUID | None
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CoASeedResult(BaseModel):
    """Outcome of seeding / migrating a tenant onto the Chart of Accounts."""

    accounts_created: int
    categories_mapped: int
    payment_accounts_mapped: int
    already_seeded: bool
