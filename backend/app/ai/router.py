"""FastAPI router for the AI module."""


import time
import uuid
from typing import Annotated

import anthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.ai.schemas import AIExtractionStatus, AIProcessResponse, HelpChatRequest, ReceiptExtractionResult
from app.ai.prompts import HELP_ASSISTANT_SYSTEM_PROMPT
from app.ai.service import process_document_ai
from app.core.exceptions import NotFoundError, RateLimitError
from app.dependencies import get_current_user, get_db, require_role
from app.documents.models import Document
from app.documents.storage import LocalStorage, StorageBackend
from sqlalchemy import select

router = APIRouter()

# ---------------------------------------------------------------------------
# Per-user AI rate limiting
# ---------------------------------------------------------------------------
_ai_requests: dict[str, tuple[int, float]] = {}
_AI_MAX_REQUESTS = 20
_AI_WINDOW_SECONDS = 60


def _check_ai_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    entry = _ai_requests.get(user_id)
    if entry is None:
        _ai_requests[user_id] = (1, now)
        return
    count, window_start = entry
    if now - window_start >= _AI_WINDOW_SECONDS:
        _ai_requests[user_id] = (1, now)
        return
    if count >= _AI_MAX_REQUESTS:
        raise RateLimitError("AI request limit exceeded. Please wait before making more requests.")
    _ai_requests[user_id] = (count + 1, window_start)


def get_storage(request: Request) -> StorageBackend:
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)


@router.post("/extract/{document_id}")
async def extract_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Trigger AI extraction on a document. Returns structured receipt/invoice data."""
    _check_ai_rate_limit(str(current_user.id))
    settings = request.app.state.settings
    start = time.monotonic()

    document, extraction = await process_document_ai(db, storage, document_id, settings)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "data": AIProcessResponse(
            document_id=document.id,
            extraction=extraction,
            processing_time_ms=elapsed_ms,
        ).model_dump(mode="json")
    }


@router.get("/extraction/{document_id}")
async def get_extraction(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get cached AI extraction results from a document's extracted_metadata field."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document", str(document_id))

    has_extraction = document.extracted_metadata is not None
    extraction = None
    if has_extraction:
        extraction = ReceiptExtractionResult.model_validate(document.extracted_metadata)

    return {
        "data": AIExtractionStatus(
            document_id=document.id,
            has_extraction=has_extraction,
            extraction=extraction,
        ).model_dump(mode="json")
    }


@router.post("/chat")
async def help_chat(
    body: HelpChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream an AI help assistant response about the platform."""
    _check_ai_rate_limit(str(current_user.id))
    settings = request.app.state.settings

    if not settings.anthropic_api_key:
        from app.core.exceptions import ValidationError
        raise ValidationError("Anthropic API key is not configured.")

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate():
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=HELP_ASSISTANT_SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
