
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.invoicing.reminder_models import ReminderChannel, ReminderStatus


# ---------------------------------------------------------------------------
# Reminder Rule schemas
# ---------------------------------------------------------------------------


class ReminderRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    days_offset: int = Field(
        description="Negative = before due, 0 = on due date, positive = after due",
    )
    channel: ReminderChannel = ReminderChannel.EMAIL
    email_subject: Optional[str] = Field(None, max_length=500)
    email_body: Optional[str] = None
    sms_body: Optional[str] = None
    is_active: bool = True


class ReminderRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    days_offset: Optional[int] = None
    channel: Optional[ReminderChannel] = None
    email_subject: Optional[str] = Field(None, max_length=500)
    email_body: Optional[str] = None
    sms_body: Optional[str] = None
    is_active: Optional[bool] = None


class ReminderRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    days_offset: int
    channel: ReminderChannel
    email_subject: Optional[str]
    email_body: Optional[str]
    sms_body: Optional[str]
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Payment Reminder (history) schemas
# ---------------------------------------------------------------------------


class PaymentReminderResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    contact_id: uuid.UUID
    reminder_rule_id: Optional[uuid.UUID]
    reminder_type: str
    channel: ReminderChannel
    status: ReminderStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Manual send request
# ---------------------------------------------------------------------------


class ManualReminderRequest(BaseModel):
    channel: ReminderChannel = ReminderChannel.EMAIL
    email_subject: Optional[str] = Field(None, max_length=500)
    email_body: Optional[str] = None
    sms_body: Optional[str] = None
