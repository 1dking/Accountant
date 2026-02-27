from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# SMTP Config
# ---------------------------------------------------------------------------

class SmtpConfigCreate(BaseModel):
    name: str = Field(..., max_length=100)
    host: str = Field(..., max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, description="Plaintext password — encrypted before storage")
    from_email: EmailStr = Field(..., max_length=255)
    from_name: str = Field(..., max_length=255)
    use_tls: bool = True
    is_default: bool = False


class SmtpConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=1)
    from_email: Optional[EmailStr] = Field(default=None, max_length=255)
    from_name: Optional[str] = Field(default=None, max_length=255)
    use_tls: Optional[bool] = None
    is_default: Optional[bool] = None


class SmtpConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    host: str
    port: int
    username: str
    from_email: str
    from_name: str
    use_tls: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

class SendInvoiceEmailRequest(BaseModel):
    invoice_id: uuid.UUID
    smtp_config_id: Optional[uuid.UUID] = None
    recipient_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    message: Optional[str] = None


class SendReminderEmailRequest(BaseModel):
    invoice_id: uuid.UUID
    smtp_config_id: Optional[uuid.UUID] = None


class TestEmailRequest(BaseModel):
    smtp_config_id: uuid.UUID
    to_email: EmailStr
