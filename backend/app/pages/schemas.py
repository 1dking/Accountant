"""Pydantic schemas for the AI page builder module."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PageCreate(BaseModel):
    title: str = Field(max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    style_preset: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None


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
