"""Pydantic schemas for manual journal entries."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.accounting.ledger_models import JournalEntryStatus


class JournalLineInput(BaseModel):
    account_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _exactly_one_side(self) -> "JournalLineInput":
        d, c = self.debit, self.credit
        if d > 0 and c > 0:
            raise ValueError("A line is either a debit or a credit, not both.")
        if d == 0 and c == 0:
            raise ValueError("A line must have a non-zero debit or credit.")
        return self


class JournalEntryCreate(BaseModel):
    date: date
    memo: str | None = None
    lines: list[JournalLineInput] = Field(min_length=2)

    @model_validator(mode="after")
    def _balanced(self) -> "JournalEntryCreate":
        debits = sum((ln.debit for ln in self.lines), Decimal("0"))
        credits = sum((ln.credit for ln in self.lines), Decimal("0"))
        if debits != credits:
            raise ValueError(
                f"Entry does not balance: debits {debits} ≠ credits {credits}."
            )
        if debits == 0:
            raise ValueError("Entry total cannot be zero.")
        return self


class JournalLineResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_code: str | None = None
    account_name: str | None = None
    debit: Decimal
    credit: Decimal
    description: str | None

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    entry_number: int
    date: date
    memo: str | None
    source: str
    source_id: str | None
    status: JournalEntryStatus
    created_by: uuid.UUID
    created_at: datetime
    lines: list[JournalLineResponse]
    total: Decimal

    model_config = {"from_attributes": True}
