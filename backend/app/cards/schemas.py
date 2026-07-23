
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_COLOR_FIELDS = ("bg_color", "text_color", "accent_color", "button_color", "button_text_color")

TEMPLATES = {"classic", "modern", "minimal", "gradient", "split", "bold"}


class CardUpdate(BaseModel):
    slug: Optional[str] = Field(None, max_length=100)
    is_published: Optional[bool] = None
    template: Optional[str] = None
    display_name: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    tagline: Optional[str] = None
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    social_links_json: Optional[str] = None
    show_org_logo: Optional[bool] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    accent_color: Optional[str] = None
    button_color: Optional[str] = None
    button_text_color: Optional[str] = None
    font: Optional[str] = Field(None, max_length=100)
    scheduling_calendar_id: Optional[uuid.UUID] = None
    show_booking: Optional[bool] = None

    @field_validator(*_COLOR_FIELDS)
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not HEX_COLOR.match(v):
            raise ValueError("Colors must be 6-digit hex like #1A2B3C")
        return v

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TEMPLATES:
            raise ValueError(f"Template must be one of: {', '.join(sorted(TEMPLATES))}")
        return v


class CardResponse(BaseModel):
    id: uuid.UUID
    slug: str
    is_published: bool
    template: str
    display_name: str
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_links_json: Optional[str] = None
    avatar_storage_path: Optional[str] = None
    show_org_logo: bool
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    accent_color: Optional[str] = None
    button_color: Optional[str] = None
    button_text_color: Optional[str] = None
    font: Optional[str] = None
    scheduling_calendar_id: Optional[uuid.UUID] = None
    show_booking: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CardAnalyticsResponse(BaseModel):
    total_views: int = 0
    unique_visitors: int = 0
    total_vcard_downloads: int = 0


class PublicCardResponse(BaseModel):
    """The public payload — palette fully resolved server-side (card
    value, else org branding, else default), plus the resolved booking
    URL and wallet availability so the public page is one fetch."""

    slug: str
    template: str
    display_name: str
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_links: dict[str, str] = {}
    avatar_url: Optional[str] = None
    logo_url: Optional[str] = None
    bg_color: str
    text_color: str
    accent_color: str
    button_color: str
    button_text_color: str
    font: str
    booking_url: Optional[str] = None
    wallet_available: dict[str, bool] = {"apple": False, "google": False}
