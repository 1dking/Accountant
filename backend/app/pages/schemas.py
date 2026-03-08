"""Pydantic schemas for the AI page builder module."""

import uuid
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field


# ── Website schemas ─────────────────────────────────────────────────────


class WebsiteCreate(BaseModel):
    name: str = Field(max_length=255)
    slug: Optional[str] = None


class WebsiteUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    domain: Optional[str] = None
    favicon_url: Optional[str] = None
    global_css: Optional[str] = None
    nav_config_json: Optional[str] = None
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    seo_defaults_json: Optional[str] = None
    tracking_pixels_json: Optional[str] = None
    is_published: Optional[bool] = None


class WebsiteResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: Optional[str] = None
    favicon_url: Optional[str] = None
    global_css: Optional[str] = None
    nav_config_json: Optional[str] = None
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    seo_defaults_json: Optional[str] = None
    tracking_pixels_json: Optional[str] = None
    is_published: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebsiteListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: Optional[str] = None
    is_published: bool
    page_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── Page schemas ────────────────────────────────────────────────────────


class PageCreate(BaseModel):
    title: str = Field(max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    style_preset: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None
    website_id: Optional[uuid.UUID] = None
    page_order: Optional[int] = None


class PageUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    js_content: Optional[str] = None
    sections_json: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image_url: Optional[str] = None
    custom_domain: Optional[str] = None
    is_homepage: Optional[bool] = None
    favicon_url: Optional[str] = None
    custom_head_html: Optional[str] = None
    style_preset: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None
    tracking_pixels_json: Optional[str] = None
    chat_history_json: Optional[str] = None
    page_order: Optional[int] = None


class PageResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    description: Optional[str] = None
    status: str
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    js_content: Optional[str] = None
    sections_json: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image_url: Optional[str] = None
    custom_domain: Optional[str] = None
    is_homepage: bool
    favicon_url: Optional[str] = None
    custom_head_html: Optional[str] = None
    style_preset: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None
    tracking_pixels_json: Optional[str] = None
    chat_history_json: Optional[str] = None
    website_id: Optional[uuid.UUID] = None
    page_order: int = 0
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageListItem(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    status: str
    is_homepage: bool
    custom_domain: Optional[str] = None
    website_id: Optional[uuid.UUID] = None
    page_order: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageVersionResponse(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    version_number: int
    change_summary: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PageAnalyticResponse(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    event_type: str
    visitor_ip: Optional[str] = None
    referrer: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PageAnalyticsSummary(BaseModel):
    total_views: int
    unique_visitors: int
    total_submissions: int
    conversion_rate: float
    views_by_day: list[dict]
    avg_time_seconds: int = 0
    bounce_rate: float = 0.0
    top_sources: list[dict] = []
    devices: dict = {}
    scroll_depth: dict = {}
    top_clicks: list[dict] = []
    utm_campaigns: list[dict] = []


# ── AI schemas ──────────────────────────────────────────────────────────


class AIGenerateRequest(BaseModel):
    prompt: str = Field(max_length=2000)
    style_preset: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None
    sections: Optional[list[str]] = None


class AIRefineRequest(BaseModel):
    page_id: uuid.UUID
    instruction: str = Field(max_length=2000)
    section_index: Optional[int] = None


class AIChatMessage(BaseModel):
    page_id: uuid.UUID
    message: str = Field(max_length=4000)


class StylePreset(BaseModel):
    id: str
    name: str
    description: str
    preview_colors: dict


class SectionTemplate(BaseModel):
    id: str
    type: str
    name: str
    description: str
    default_html: str


# ── Analytics tracking ──────────────────────────────────────────────────


class TrackEventRequest(BaseModel):
    page_id: uuid.UUID
    visitor_id: str
    session_id: str
    event_type: str  # page_view, scroll_25, scroll_50, scroll_75, scroll_100, click, form_submit, time_on_page
    event_data: Optional[dict] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    user_agent: Optional[str] = None


# ── Video upload ────────────────────────────────────────────────────────


# ── Template schemas ────────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str = Field(max_length=255)
    description: Optional[str] = None
    category_industry: Optional[str] = None
    category_type: Optional[str] = None
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    metadata_json: Optional[str] = None
    scope: str = "org"  # org | platform
    source_page_id: Optional[uuid.UUID] = None  # if saving from existing page


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category_industry: Optional[str] = None
    category_type: Optional[str] = None
    thumbnail_url: Optional[str] = None
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    metadata_json: Optional[str] = None
    scope: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    category_industry: Optional[str] = None
    category_type: Optional[str] = None
    thumbnail_url: Optional[str] = None
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    metadata_json: Optional[str] = None
    scope: str
    is_active: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    category_industry: Optional[str] = None
    category_type: Optional[str] = None
    thumbnail_url: Optional[str] = None
    scope: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoUploadResponse(BaseModel):
    mp4_url: str
    webm_url: str
    poster_url: str
    duration_seconds: float = 0
