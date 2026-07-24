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
    user_name: str
    user_email: str
    permission: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Version history schemas
# ---------------------------------------------------------------------------


class VersionListItem(BaseModel):
    """Version list entries omit content_json — it can be large and the
    list view only needs to know what versions exist."""

    id: uuid.UUID
    version_number: int
    title: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VersionResponse(VersionListItem):
    content_json: dict | None = None


# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------


class CommentCreate(BaseModel):
    content: str
    parent_id: uuid.UUID | None = None
    mentioned_user_ids: list[uuid.UUID] = Field(default_factory=list)


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    parent_id: uuid.UUID | None
    content: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# AI writing assistant
# ---------------------------------------------------------------------------


class AIAssistRequest(BaseModel):
    instruction: str = Field(
        ..., description="What the user wants, e.g. 'make this more concise' or a direct question"
    )
    selected_text: str | None = Field(
        default=None, description="The user's current editor selection, if any"
    )


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
    content_json: dict | None = Field(
        default=None, description="Optional starter content (e.g. template seeding)"
    )

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
    content_json: dict | None = None


class OfficeDocResponse(BaseModel):
    id: uuid.UUID
    title: str
    doc_type: str
    created_by: uuid.UUID
    folder_id: uuid.UUID | None
    is_starred: bool
    is_trashed: bool
    content_text: str | None = None
    content_json: dict | None = None
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
