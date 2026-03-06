
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Twilio Phone Numbers
# ---------------------------------------------------------------------------


class TwilioPhoneNumberCreate(BaseModel):
    phone_number: str = Field(max_length=20)
    friendly_name: Optional[str] = Field(None, max_length=255)
    capabilities_json: Optional[str] = None


class TwilioPhoneNumberUpdate(BaseModel):
    friendly_name: Optional[str] = Field(None, max_length=255)
    assigned_user_id: Optional[uuid.UUID] = None


class TwilioPhoneNumberResponse(BaseModel):
    id: uuid.UUID
    phone_number: str
    assigned_user_id: Optional[uuid.UUID]
    friendly_name: Optional[str]
    capabilities_json: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Call Logs
# ---------------------------------------------------------------------------


class CallLogCreate(BaseModel):
    contact_id: Optional[uuid.UUID] = None
    direction: str = Field(max_length=10)
    from_number: str = Field(max_length=20)
    to_number: str = Field(max_length=20)
    duration_seconds: int = 0
    recording_url: Optional[str] = None
    status: str = Field(max_length=20)
    notes: Optional[str] = None
    outcome: Optional[str] = Field(None, max_length=50)


class CallLogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    contact_id: Optional[uuid.UUID]
    direction: str
    from_number: str
    to_number: str
    duration_seconds: int
    recording_url: Optional[str]
    status: str
    notes: Optional[str]
    outcome: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# SMS Messages
# ---------------------------------------------------------------------------


class SmsMessageCreate(BaseModel):
    to_number: str = Field(max_length=20)
    body: str


class SmsMessageResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    contact_id: Optional[uuid.UUID]
    direction: str
    from_number: str
    to_number: str
    body: str
    status: str
    twilio_sid: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Live Chat
# ---------------------------------------------------------------------------


class LiveChatSessionCreate(BaseModel):
    visitor_name: Optional[str] = Field(None, max_length=255)
    visitor_email: Optional[str] = Field(None, max_length=255)


class LiveChatSessionResponse(BaseModel):
    id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    visitor_name: Optional[str]
    visitor_email: Optional[str]
    status: str
    assigned_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LiveChatMessageCreate(BaseModel):
    direction: str = Field(max_length=10)
    message: str


class LiveChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    direction: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class MissedCallConfig(BaseModel):
    enabled: bool = False
    message: str = "Sorry we missed your call. We will get back to you shortly."


class CapabilityTokenResponse(BaseModel):
    token: str
