"""Pydantic schemas for O-Brain AI module."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    page_context: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    tools_used: list[str] | None = None
    sources_cited: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    messages: list[ChatMessageResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class KnowledgeAddRequest(BaseModel):
    content: str
    title: str = ""
    category: str = "general"


class KnowledgeItemResponse(BaseModel):
    id: uuid.UUID
    content: str
    source_type: str
    metadata_json: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

class TranscriptResponse(BaseModel):
    id: uuid.UUID
    meeting_id: Optional[uuid.UUID] = None
    full_text: Optional[str] = None
    summary: Optional[str] = None
    action_items: list[dict] | None = None
    financial_commitments: list[dict] | None = None
    language: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptionQueueResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    source_id: str
    status: str
    attempts: int
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Audio recording upload
# ---------------------------------------------------------------------------

class RecordingUploadRequest(BaseModel):
    contact_id: Optional[str] = None
    title: Optional[str] = None


# ---------------------------------------------------------------------------
# Proactive alerts
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id: uuid.UUID
    alert_type: str
    title: str
    message: str
    data_json: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyBriefingResponse(BaseModel):
    greeting: str
    alerts: list[AlertResponse]
    summary: str


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action_type: str
    ai_input: Optional[str] = None
    ai_output: Optional[str] = None
    human_decision: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class OnboardingAnswerRequest(BaseModel):
    answers: list[dict]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class BrainSearchRequest(BaseModel):
    query: str
    source_type: str | None = None
    source_types: list[str] | None = None
    contact_id: Optional[str] = None
    limit: int = 10


class BrainSearchResult(BaseModel):
    content: str
    source_type: str
    source_id: Optional[str] = None
    relevance_score: float
    metadata: Optional[dict] = None
