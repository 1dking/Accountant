
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MODES = {"floating", "inline"}
POSITIONS = {"bottom-right", "bottom-left"}


class WidgetConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    mode: Optional[str] = None
    position: Optional[str] = None
    button_color: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    greeting_title: Optional[str] = Field(None, max_length=255)
    greeting_message: Optional[str] = None
    success_message: Optional[str] = None
    collect_phone: Optional[bool] = None

    @field_validator("button_color", "bg_color", "text_color")
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not HEX_COLOR.match(v):
            raise ValueError("Colors must be 6-digit hex like #1A2B3C")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(MODES))}")
        return v

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in POSITIONS:
            raise ValueError(f"position must be one of: {', '.join(sorted(POSITIONS))}")
        return v


class WidgetConfigResponse(BaseModel):
    id: uuid.UUID
    widget_key: str
    is_enabled: bool
    mode: str
    position: str
    button_color: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    greeting_title: Optional[str] = None
    greeting_message: Optional[str] = None
    success_message: Optional[str] = None
    collect_phone: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublicWidgetConfig(BaseModel):
    """Theme/copy payload the /embed/{key} page fetches — never includes
    widget_key (already known to the caller) or the linked form's
    webhook_key."""

    mode: str
    position: str
    button_color: str
    bg_color: str
    text_color: str
    greeting_title: str
    greeting_message: str
    collect_phone: bool


class WidgetSubmitRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    message: Optional[str] = None
    # Honeypot — a real browser never fills a field hidden via CSS; a
    # naive bot filling every input trips this.
    website: Optional[str] = None
