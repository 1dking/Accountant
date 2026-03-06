import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PortalLoginRequest(BaseModel):
    email: str
    password: str


class PortalDashboard(BaseModel):
    contact_name: Optional[str]
    company_name: str
    pending_invoices: int
    total_outstanding: float
    pending_proposals: int
    shared_files: int
    upcoming_meetings: int


class PortalInvoice(BaseModel):
    id: uuid.UUID
    invoice_number: str
    issue_date: str
    due_date: str
    total: float
    currency: str
    status: str
    payment_url: Optional[str] = None


class PortalProposal(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    total: Optional[float]
    created_at: datetime
    signing_token: Optional[str] = None


class PortalFile(BaseModel):
    share_id: uuid.UUID
    file_id: uuid.UUID
    filename: str
    mime_type: str
    file_size: int
    permission: str
    shared_at: datetime


class PortalMeeting(BaseModel):
    id: uuid.UUID
    title: str
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    status: str
