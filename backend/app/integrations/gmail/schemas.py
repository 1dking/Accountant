from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime


class GmailConnectResponse(BaseModel):
    auth_url: str


class GmailScanRequest(BaseModel):
    gmail_account_id: uuid.UUID
    query: str | None = "has:attachment (invoice OR receipt OR payment)"
    max_results: int = 50


class GmailScanResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: str
    subject: str | None
    sender: str | None
    date: datetime | None
    snippet: str | None
    has_attachments: bool
    is_processed: bool
    matched_invoice_id: uuid.UUID | None
    matched_document_id: uuid.UUID | None
    created_at: datetime


class GmailSendRequest(BaseModel):
    gmail_account_id: uuid.UUID
    to: str
    subject: str
    body_html: str
    attachment_paths: list[str] | None = None
