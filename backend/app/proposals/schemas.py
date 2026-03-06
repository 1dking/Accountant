"""Pydantic schemas for the proposals module."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.proposals.models import ProposalStatus, PaymentStatus, SyncDirection, SyncStatus


# ---------------------------------------------------------------------------
# Proposal Content Block schemas (for the editor JSON)
# ---------------------------------------------------------------------------

class ContentBlock(BaseModel):
    """A single block in the proposal editor."""
    id: str  # client-generated UUID
    type: str  # "text", "image", "video", "pricing_table", "custom_value", "signature", "page_break"
    data: dict = Field(default_factory=dict)
    order: int = 0


# ---------------------------------------------------------------------------
# Proposal Recipient schemas
# ---------------------------------------------------------------------------

class RecipientCreate(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="signer", max_length=50)
    signing_order: int = Field(default=1, ge=1)


class RecipientResponse(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    email: str
    name: str
    role: str
    signing_order: int
    signed_at: datetime | None
    signature_type: str | None
    document_hash: str | None
    ip_address: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Proposal Activity schemas
# ---------------------------------------------------------------------------

class ActivityResponse(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    action: str
    actor_email: str | None
    actor_name: str | None
    ip_address: str | None
    metadata_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Proposal Template schemas
# ---------------------------------------------------------------------------

class TemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(None, max_length=1000)
    content_json: str  # JSON string of blocks


class TemplateUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=1000)
    content_json: str | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    content_json: str
    thumbnail_url: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    thumbnail_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Proposal schemas
# ---------------------------------------------------------------------------

class ProposalCreate(BaseModel):
    contact_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    content_json: str = Field(default="[]")  # JSON array of ContentBlock
    value: Decimal = Field(default=Decimal("0.00"))
    currency: str = Field(default="USD", max_length=3)
    template_id: uuid.UUID | None = None
    collect_payment: bool = False
    payment_mode: str | None = Field(None, max_length=20)  # "one_time" or "recurring"
    payment_frequency: str | None = Field(None, max_length=20)
    recipients: list[RecipientCreate] = Field(default_factory=list)
    follow_up_enabled: bool = True
    follow_up_hours: int = Field(default=48, ge=1)


class ProposalUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content_json: str | None = None
    value: Decimal | None = None
    currency: str | None = Field(None, max_length=3)
    contact_id: uuid.UUID | None = None
    status: ProposalStatus | None = None
    collect_payment: bool | None = None
    payment_mode: str | None = None
    payment_frequency: str | None = None
    follow_up_enabled: bool | None = None
    follow_up_hours: int | None = None


class ProposalResponse(BaseModel):
    id: uuid.UUID
    proposal_number: str
    contact_id: uuid.UUID
    title: str
    content_json: str
    status: ProposalStatus
    value: Decimal
    currency: str
    template_id: uuid.UUID | None
    collect_payment: bool
    payment_mode: str | None
    payment_frequency: str | None
    payment_status: PaymentStatus | None
    public_token: str | None
    created_by: uuid.UUID
    sent_at: datetime | None
    viewed_at: datetime | None
    signed_at: datetime | None
    paid_at: datetime | None
    follow_up_enabled: bool
    follow_up_hours: int
    contact: "ContactResponse | None" = None  # from contacts schemas
    recipients: list[RecipientResponse] = []
    activities: list[ActivityResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProposalListItem(BaseModel):
    id: uuid.UUID
    proposal_number: str
    contact_id: uuid.UUID
    title: str
    status: ProposalStatus
    value: Decimal
    currency: str
    payment_status: PaymentStatus | None
    public_token: str | None
    created_by: uuid.UUID
    sent_at: datetime | None
    viewed_at: datetime | None
    signed_at: datetime | None
    paid_at: datetime | None
    contact: "ContactResponse | None" = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProposalFilter(BaseModel):
    search: str | None = None
    status: ProposalStatus | None = None
    contact_id: uuid.UUID | None = None
    payment_status: PaymentStatus | None = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    value_min: Decimal | None = None
    value_max: Decimal | None = None


class ProposalDashboardStats(BaseModel):
    total_proposals: int
    draft_count: int
    sent_count: int
    viewed_count: int
    signed_count: int
    declined_count: int
    paid_count: int
    total_value: Decimal
    signed_value: Decimal
    paid_value: Decimal


# ---------------------------------------------------------------------------
# E-Signature schemas
# ---------------------------------------------------------------------------

class SignProposalRequest(BaseModel):
    """Submitted by a recipient to sign a proposal."""
    recipient_id: uuid.UUID
    signature_data: str  # base64 drawn signature or typed name
    signature_type: str = Field(default="drawn", pattern=r"^(drawn|typed)$")


class SigningPageData(BaseModel):
    """Data returned for the public signing page."""
    proposal_id: uuid.UUID
    proposal_title: str
    content_json: str
    recipient_name: str
    recipient_email: str
    recipient_role: str
    already_signed: bool
    all_signed: bool
    contact_name: str | None = None
    company_name: str | None = None


# ---------------------------------------------------------------------------
# GHL Sync schemas
# ---------------------------------------------------------------------------

class GhlSyncLogResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    ghl_entity_id: str | None
    direction: SyncDirection
    status: SyncStatus
    error_message: str | None
    synced_at: datetime

    model_config = {"from_attributes": True}


class GhlSettingsResponse(BaseModel):
    connected: bool
    ghl_location_id: str | None
    last_sync_at: datetime | None
    sync_count: int


class GhlManualSyncRequest(BaseModel):
    entity_type: str = Field(pattern=r"^(contacts|invoices|deals)$")
    direction: str = Field(pattern=r"^(push|pull)$")


# ---------------------------------------------------------------------------
# Follow-up schemas
# ---------------------------------------------------------------------------

class FollowUpRuleCreate(BaseModel):
    resource_type: str = Field(pattern=r"^(proposal|invoice)$")
    resource_id: uuid.UUID
    trigger_event: str = Field(pattern=r"^(not_signed|overdue)$")
    delay_hours: int = Field(default=48, ge=1)
    message_template: str | None = None
    channel: str = Field(default="email", pattern=r"^(email|sms)$")


class FollowUpRuleResponse(BaseModel):
    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    trigger_event: str
    delay_hours: int
    message_template: str | None
    channel: str
    is_active: bool
    last_sent_at: datetime | None
    send_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Import ContactResponse at bottom to avoid circular imports
from app.contacts.schemas import ContactResponse  # noqa: E402
