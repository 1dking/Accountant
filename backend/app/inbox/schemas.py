
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.inbox.models import MessageDirection, MessageType


class UnifiedMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    message_type: MessageType
    direction: MessageDirection
    subject: Optional[str]
    body: Optional[str]
    recipient: Optional[str]
    sender: Optional[str]
    is_read: bool
    thread_id: Optional[str]
    source_type: Optional[str]
    source_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class SendReplyRequest(BaseModel):
    body: str = Field(..., min_length=1)
    subject: Optional[str] = None
    smtp_config_id: Optional[uuid.UUID] = None


class UnreadCount(BaseModel):
    total: int
    email: int
    sms: int
