"""Pydantic schemas for the reconciliation module."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Match schemas
# ---------------------------------------------------------------------------


class MatchResponse(BaseModel):
    """Full match record with joined receipt and transaction summary fields."""

    id: uuid.UUID
    receipt_id: uuid.UUID
    transaction_id: uuid.UUID
    match_confidence: float
    match_reason: Optional[str] = None
    status: str
    confirmed_by: Optional[uuid.UUID] = None
    confirmed_at: Optional[datetime] = None

    # Joined receipt (Expense) fields
    receipt_vendor: Optional[str] = None
    receipt_amount: float = 0.0
    receipt_date: str = ""

    # Joined transaction (CashbookEntry) fields
    transaction_description: str = ""
    transaction_amount: float = 0.0
    transaction_date: str = ""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManualMatchRequest(BaseModel):
    """Request body for creating a manual match between a receipt and transaction."""

    receipt_id: uuid.UUID
    transaction_id: uuid.UUID


class ReconciliationSummary(BaseModel):
    """High-level reconciliation statistics."""

    pending_matches: int = 0
    confirmed_matches: int = 0
    unmatched_receipts: int = 0
    unmatched_transactions: int = 0
    total_matched_amount: float = 0.0


class FindMatchesRequest(BaseModel):
    """Optional date range filter for the find-matches algorithm."""

    date_from: Optional[str] = None
    date_to: Optional[str] = None
