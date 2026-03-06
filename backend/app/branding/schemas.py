"""Pydantic schemas for universal branding settings."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BrandingUpdate(BaseModel):
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font_heading: Optional[str] = None
    font_body: Optional[str] = None
    border_radius: Optional[str] = None
    custom_css: Optional[str] = None
    email_header_html: Optional[str] = None
    email_footer_html: Optional[str] = None
    portal_welcome_message: Optional[str] = None
    booking_page_header: Optional[str] = None
    org_slug: Optional[str] = None


class BrandingResponse(BaseModel):
    id: uuid.UUID
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_heading: str
    font_body: str
    border_radius: str
    custom_css: Optional[str] = None
    email_header_html: Optional[str] = None
    email_footer_html: Optional[str] = None
    portal_welcome_message: Optional[str] = None
    booking_page_header: Optional[str] = None
    org_slug: Optional[str] = None
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublicBrandingResponse(BaseModel):
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_heading: str
    font_body: str
    border_radius: str
    portal_welcome_message: Optional[str] = None
    booking_page_header: Optional[str] = None
    org_slug: Optional[str] = None

    model_config = {"from_attributes": True}
