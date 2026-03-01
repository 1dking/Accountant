import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PublicTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    token: str
    resource_type: str
    resource_id: uuid.UUID
    expires_at: datetime | None
    is_active: bool
    view_count: int
    shareable_url: str  # computed in router before returning


class CreatePublicTokenRequest(BaseModel):
    expires_in_days: int | None = None  # optional expiry


class PublicDocumentResponse(BaseModel):
    """Response for public document viewing -- includes everything needed to render."""

    resource_type: str
    document: dict  # the estimate or invoice data
    company: dict | None  # company branding info
    actions: list[str]  # available actions: "accept", "pay", "decline"
    is_signed: bool
    stripe_configured: bool


class AcceptEstimateRequest(BaseModel):
    signature_data: str  # base64 PNG
    signer_name: str
