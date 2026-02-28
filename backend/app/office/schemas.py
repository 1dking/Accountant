"""Pydantic schemas for the office module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Collaborator schemas
# ---------------------------------------------------------------------------


class CollaboratorResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    permission: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Share request
# ---------------------------------------------------------------------------


class ShareRequest(BaseModel):
    user_id: uuid.UUID
    permission: str = "edit"


# ---------------------------------------------------------------------------
# Office Document schemas
# ---------------------------------------------------------------------------


class OfficeDocCreate(BaseModel):
    title: str = "Untitled"
    doc_type: str = Field(..., description="document, spreadsheet, or presentation")
    folder_id: uuid.UUID | None = None

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        allowed = {"document", "spreadsheet", "presentation"}
        if v not in allowed:
            raise ValueError(f"doc_type must be one of {allowed}")
        return v


class OfficeDocUpdate(BaseModel):
    title: str | None = None
    folder_id: uuid.UUID | None = None
    is_starred: bool | None = None


class OfficeDocResponse(BaseModel):
    id: uuid.UUID
    title: str
    doc_type: str
    created_by: uuid.UUID
    folder_id: uuid.UUID | None
    is_starred: bool
    is_trashed: bool
    content_text: str | None = None
    last_accessed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    collaborators: list[CollaboratorResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("content_text", mode="before")
    @classmethod
    def truncate_content_text(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 200:
            return v[:200]
        return v


class OfficeDocListItem(BaseModel):
    id: uuid.UUID
    title: str
    doc_type: str
    created_by: uuid.UUID
    folder_id: uuid.UUID | None
    is_starred: bool
    last_accessed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Star request
# ---------------------------------------------------------------------------


class StarRequest(BaseModel):
    starred: bool
