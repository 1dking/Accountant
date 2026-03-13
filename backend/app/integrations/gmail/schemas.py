
from typing import Optional

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class GmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    last_sync_at: Optional[datetime]
    created_at: datetime


class GmailConnectResponse(BaseModel):
    auth_url: str


class GmailScanRequest(BaseModel):
    gmail_account_id: uuid.UUID
    query: Optional[str] = "has:attachment (invoice OR receipt OR payment)"
    max_results: int = 50
    after_date: Optional[date] = None
    before_date: Optional[date] = None
    page_token: Optional[str] = None


class GmailScanResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: str
    subject: Optional[str]
    sender: Optional[str]
    date: Optional[datetime]
    snippet: Optional[str]
    body_text: Optional[str] = None
    has_attachments: bool
    is_processed: bool
    is_skipped: bool = False
    matched_invoice_id: Optional[uuid.UUID] = None
    matched_document_id: Optional[uuid.UUID] = None
    matched_expense_id: Optional[uuid.UUID] = None
    matched_income_id: Optional[uuid.UUID] = None
    created_at: datetime


class GmailSendRequest(BaseModel):
    gmail_account_id: uuid.UUID
    to: str
    subject: str
    body_html: str
    attachment_paths: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Import flow
# ---------------------------------------------------------------------------


class EmailImportRequest(BaseModel):
    """Pre-filled data for importing an email as an expense or income record."""
    record_type: str = Field(
        "expense", pattern=r"^(expense|income)$",
        description="Whether to create an expense or income record",
    )
    vendor_name: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None)
    currency: str = "USD"
    date: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    income_category: Optional[str] = None
    notes: Optional[str] = None
    account_id: Optional[uuid.UUID] = None
    is_recurring: bool = False
    recurring_frequency: Optional[str] = None  # weekly/monthly/quarterly/yearly
    recurring_next_date: Optional[str] = None


class EmailImportResponse(BaseModel):
    """Response from the import flow."""
    document_id: Optional[str] = None
    expense_id: Optional[str] = None
    income_id: Optional[str] = None
    parsed_data: Optional[dict] = None


class EmailParseResponse(BaseModel):
    """Parsed data extracted from email for the confirmation modal."""
    vendor_name: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str = "USD"
    date: Optional[date] = None
    description: Optional[str] = None
    category_suggestion: Optional[str] = None
    record_type: str = "expense"
    attachments: list[dict] = []


class GmailResultsListRequest(BaseModel):
    """Filters for listing scan results with pagination."""
    gmail_account_id: Optional[uuid.UUID] = None
    is_processed: Optional[bool] = None
    has_attachments: Optional[bool] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 50


class BulkDeleteRequest(BaseModel):
    """Request to delete multiple scan results."""
    result_ids: list[uuid.UUID]
