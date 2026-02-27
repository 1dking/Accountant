"""Pydantic schemas for the documents module."""


from typing import Optional

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.documents.models import DocumentStatus, DocumentType

# ---------------------------------------------------------------------------
# Tag schemas
# ---------------------------------------------------------------------------


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Folder schemas
# ---------------------------------------------------------------------------


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)


class FolderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)


class FolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderTreeResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    children: list["FolderTreeResponse"] = []

    model_config = {"from_attributes": True}


FolderTreeResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Document version schemas
# ---------------------------------------------------------------------------


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    filename: str
    file_size: int
    file_hash: str
    storage_path: str
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    file_hash: str
    document_type: DocumentType
    status: DocumentStatus
    title: str | None
    folder_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    file_hash: str
    storage_path: str
    folder_id: uuid.UUID | None
    document_type: DocumentType
    status: DocumentStatus
    title: str | None
    description: str | None
    extracted_text: str | None
    extracted_metadata: dict | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    folder: FolderResponse | None = None
    tags: list[TagResponse] = []
    versions: list[DocumentVersionResponse] = []

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """Lighter schema for list endpoints -- omits extracted_text."""

    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    file_hash: str
    folder_id: uuid.UUID | None
    document_type: DocumentType
    status: DocumentStatus
    title: str | None
    description: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    folder: FolderResponse | None = None
    tags: list[TagResponse] = []

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    title: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=2000)
    document_type: DocumentType | None = None
    folder_id: uuid.UUID | None = None
    status: DocumentStatus | None = None


# ---------------------------------------------------------------------------
# Document filter schema
# ---------------------------------------------------------------------------


class DocumentFilter(BaseModel):
    search: str | None = None
    folder_id: uuid.UUID | None = None
    document_type: DocumentType | None = None
    tag: str | None = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    uploaded_by: uuid.UUID | None = None
    status: DocumentStatus | None = None


# ---------------------------------------------------------------------------
# Quick Capture (mobile receipt capture)
# ---------------------------------------------------------------------------


class QuickCaptureResponse(BaseModel):
    document_id: uuid.UUID
    document_title: str
    extraction: dict | None = None
    expense_id: uuid.UUID | None = None
    expense_amount: float | None = None
    expense_vendor: str | None = None
    expense_date: str | None = None
    processing_time_ms: int
