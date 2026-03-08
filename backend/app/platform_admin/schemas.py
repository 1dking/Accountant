"""Pydantic schemas for platform administration."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Feature flags ────────────────────────────────────────────────────────

class FeatureFlagResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool
    category: str
    updated_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeatureFlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    description: Optional[str] = None


class FeatureFlagCreate(BaseModel):
    key: str = Field(max_length=100)
    name: str = Field(max_length=255)
    description: Optional[str] = None
    enabled: bool = True
    category: str = "general"


# ── Platform settings ────────────────────────────────────────────────────

class PlatformSettingResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: Optional[str] = None
    category: str
    description: Optional[str] = None
    value_type: str
    updated_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformSettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None


class PlatformSettingCreate(BaseModel):
    key: str = Field(max_length=100)
    value: Optional[str] = None
    category: str = "general"
    description: Optional[str] = None
    value_type: str = "string"


# ── Dashboard metrics ────────────────────────────────────────────────────

class DashboardMetrics(BaseModel):
    total_users: int = 0
    active_users: int = 0
    total_pages: int = 0
    published_pages: int = 0
    total_documents: int = 0
    storage_used_bytes: int = 0
    total_invoices: int = 0
    total_revenue: float = 0.0
    total_contacts: int = 0
    total_proposals: int = 0
    total_expenses: float = 0.0
    total_meetings: int = 0
    active_split_tests: int = 0
    users_by_role: dict = {}
    registrations_by_day: list[dict] = []
    activity_by_day: list[dict] = []
    recent_activity: list[dict] = []


# ── Health check ─────────────────────────────────────────────────────────

class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    status: str = "unknown"  # healthy, degraded, down, unconfigured


class SystemHealth(BaseModel):
    status: str  # healthy, degraded, down
    database: str = "healthy"
    storage: str = "healthy"
    uptime_seconds: int = 0
    integrations: list[IntegrationStatus] = []
    error_count_24h: int = 0
    warning_count_24h: int = 0


# ── Error log ────────────────────────────────────────────────────────────

class ErrorLogResponse(BaseModel):
    id: uuid.UUID
    level: str
    source: str
    message: str
    traceback: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    resolved: bool
    resolved_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User management (enhanced) ──────────────────────────────────────────

class UserDetail(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    page_count: int = 0
    document_count: int = 0
    invoice_count: int = 0
    activity_count: int = 0
    recent_activity: list[dict] = []

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    auth_provider: str
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── API key status ───────────────────────────────────────────────────────

class ApiKeyStatus(BaseModel):
    integration: str
    configured: bool
    masked_key: Optional[str] = None
    fields: list[dict] = []
