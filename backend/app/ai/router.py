"""FastAPI router for the AI module."""


import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.ai.schemas import AIExtractionStatus, AIProcessResponse, ReceiptExtractionResult
from app.ai.service import process_document_ai
from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db, require_role
from app.documents.models import Document
from app.documents.storage import LocalStorage, StorageBackend
from sqlalchemy import select

router = APIRouter()


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
