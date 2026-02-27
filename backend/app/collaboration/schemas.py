from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.collaboration.models import ApprovalStatus


# ── Comments ──────────────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    parent_id: uuid.UUID | None = None


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    parent_id: uuid.UUID | None = None
    content: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Activity ──────────────────────────────────────────────────────────────────


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityFilter(BaseModel):
    user_id: uuid.UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


# ── Approvals ─────────────────────────────────────────────────────────────────


class ApprovalRequest(BaseModel):
    assigned_to: uuid.UUID


class ApprovalResolve(BaseModel):
    status: ApprovalStatus = Field(
        ..., description="Must be 'approved' or 'rejected'"
    )
    comment: str | None = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    requested_by: uuid.UUID
    assigned_to: uuid.UUID
    status: ApprovalStatus
    comment: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}
