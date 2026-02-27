
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SendSmsRequest(BaseModel):
    to: str
    message: str


class SendInvoiceSmsRequest(BaseModel):
    invoice_id: uuid.UUID
    to: str | None = None


class SmsLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient: str
    message: str
    status: str
    direction: str
    related_invoice_id: uuid.UUID | None = None
    twilio_sid: str | None = None
    created_at: datetime
