
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    fields_json: str
    thank_you_type: str = Field(default="message", max_length=50)
    thank_you_config_json: Optional[str] = None
    style_json: Optional[str] = None


class FormUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    fields_json: Optional[str] = None
    thank_you_type: Optional[str] = Field(None, max_length=50)
    thank_you_config_json: Optional[str] = None
    style_json: Optional[str] = None
    is_active: Optional[bool] = None


class FormResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    fields_json: str
    thank_you_type: str
    thank_you_config_json: Optional[str]
    style_json: Optional[str]
    is_active: bool
    webhook_key: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookKeyResponse(BaseModel):
    """Returned after generating/rotating the inbound webhook key."""

    form_id: uuid.UUID
    webhook_key: str
    # The full URL to hand to the external website, prebuilt so the UI can just
    # display + copy it.
    webhook_url: str


class FormListItem(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    submission_count: int
    last_submission_at: Optional[datetime]
    created_at: datetime


class FormSubmissionResponse(BaseModel):
    id: uuid.UUID
    form_id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    data_json: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


class PublicFormResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    fields_json: str
    style_json: Optional[str]
    thank_you_type: str
    thank_you_config_json: Optional[str]

    model_config = {"from_attributes": True}


class FormSubmitRequest(BaseModel):
    data: dict[str, Any]
