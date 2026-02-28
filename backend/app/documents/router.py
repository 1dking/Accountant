"""FastAPI router for the documents module."""


import io
import logging
import uuid
from typing import Annotated, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role
from app.documents.models import DocumentStatus, DocumentType
from app.documents.schemas import (
    DocumentFilter,
    DocumentListItem,
    DocumentResponse,
    DocumentUpdate,
    DocumentUploadResponse,
    DocumentVersionResponse,
    FolderCreate,
    FolderResponse,
    FolderTreeResponse,
    FolderUpdate,
    QuickCaptureResponse,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.documents.service import (
    add_tags_to_document,
    create_folder,
    create_tag,
    delete_document,
    delete_folder,
    delete_tag,
    download_document,
    get_document,
    get_document_versions,
    get_folder_tree,
    list_documents,
    list_tags,
    quick_capture,
    remove_tag_from_document,
    search_documents,
    update_document,
    update_folder,
    update_tag,
    upload_document,
    upload_version,
)
from app.documents.storage import LocalStorage, StorageBackend

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency: storage backend
# ---------------------------------------------------------------------------


def get_storage(request: Request) -> StorageBackend:
    """Resolve the storage backend from application settings."""
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)


async def _run_ai_extraction(document_id: uuid.UUID, storage_path: str, settings) -> None:
    """Background task: run AI extraction on a newly uploaded document."""
    from app.ai.service import process_document_ai
    from app.database import build_engine, build_session_factory

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    try:
        async with session_factory() as db:
            storage = LocalStorage(settings.storage_path)
            await process_document_ai(db, storage, document_id, settings)
            logger.info("Auto-extraction completed for document %s", document_id)
    except Exception:
        logger.exception("Auto-extraction failed for document %s", document_id)
    finally:
        await engine.dispose()


@router.post("/upload", status_code=201)
async def upload(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
    folder_id: uuid.UUID | None = None,
    document_type: DocumentType = DocumentType.OTHER,
    title: str | None = None,
    tags: List[str] = Form(default=[]),
) -> dict:
    """Upload a new document with optional tags. Auto-triggers AI extraction."""
    file_data = await file.read()
    settings = request.app.state.settings

    document = await upload_document(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        user=current_user,
        folder_id=folder_id,
        settings=settings,
        document_type=document_type.value,
        title=title,
    )

    # Apply tags if provided (tags are sent as UUID strings from the frontend)
    if tags:
        tag_uuids = [uuid.UUID(t) for t in tags if t]
        if tag_uuids:
            await add_tags_to_document(db, document.id, tag_uuids, current_user)
            await db.refresh(document)

    # Auto-trigger AI extraction in background
    from app.ai.service import EXTRACTABLE_MIME_TYPES

    if document.mime_type in EXTRACTABLE_MIME_TYPES and settings.anthropic_api_key:
        background_tasks.add_task(
            _run_ai_extraction, document.id, document.storage_path, settings
        )

    return {"data": DocumentUploadResponse.model_validate(document)}


@router.post("/quick-capture", status_code=201)
async def quick_capture_endpoint(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
) -> dict:
    """Upload a receipt, run AI extraction, and create an expense in one call.

    Designed for mobile receipt capture -- chains upload, AI extraction, and
    expense creation into a single request.  Each step is independent: if AI
    extraction fails the document is still saved, and if expense creation fails
    the document + extraction are still saved.
    """
    file_data = await file.read()
    settings = request.app.state.settings

    document, extraction, expense, elapsed_ms = await quick_capture(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=file.filename or "receipt.jpg",
        content_type=file.content_type or "image/jpeg",
        user=current_user,
        settings=settings,
    )

    return {
        "data": QuickCaptureResponse(
            document_id=document.id,
            document_title=document.title or document.original_filename,
            extraction=extraction,
            expense_id=expense.id if expense else None,
            expense_amount=expense.amount if expense else None,
            expense_vendor=expense.vendor_name if expense else None,
            expense_date=str(expense.date) if expense else None,
            processing_time_ms=elapsed_ms,
        )
    }


@router.get("/")
async def list_docs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = None,
    folder_id: uuid.UUID | None = None,
    document_type: DocumentType | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    uploaded_by: uuid.UUID | None = None,
    status: DocumentStatus | None = None,
) -> dict:
    """List documents with filtering and pagination."""
    filters = DocumentFilter(
        search=search,
        folder_id=folder_id,
        document_type=document_type,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
        uploaded_by=uploaded_by,
        status=status,
    )
    documents, meta = await list_documents(db, filters, pagination)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": meta,
    }


@router.get("/search")
async def search(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str = Query(..., min_length=1, description="Search query"),
) -> dict:
    """Search documents by filename, title, or extracted text."""
    documents, meta = await search_documents(db, q, pagination)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": meta,
    }


@router.get("/folders")
async def list_folders(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return the folder tree (root folders with nested children)."""
    folders = await get_folder_tree(db)
    return {"data": [FolderTreeResponse.model_validate(f) for f in folders]}


@router.post("/folders", status_code=201)
async def create_folder_endpoint(
    data: FolderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a new folder."""
    folder = await create_folder(db, data, current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.put("/folders/{folder_id}")
async def update_folder_endpoint(
    folder_id: uuid.UUID,
    data: FolderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update a folder."""
    folder = await update_folder(db, folder_id, data, current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.delete("/folders/{folder_id}")
async def delete_folder_endpoint(
    folder_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Delete a folder (admin only)."""
    await delete_folder(db, folder_id, current_user)
    return {"data": {"message": "Folder deleted successfully"}}


@router.get("/tags")
async def list_tags_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return all tags."""
    tags = await list_tags(db)
    return {"data": [TagResponse.model_validate(t) for t in tags]}


@router.post("/tags", status_code=201)
async def create_tag_endpoint(
    data: TagCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a new tag."""
    tag = await create_tag(db, data)
    return {"data": TagResponse.model_validate(tag)}


@router.put("/tags/{tag_id}")
async def update_tag_endpoint(
    tag_id: uuid.UUID,
    data: TagUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update a tag."""
    tag = await update_tag(db, tag_id, data)
    return {"data": TagResponse.model_validate(tag)}


@router.delete("/tags/{tag_id}")
async def delete_tag_endpoint(
    tag_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Delete a tag (admin only)."""
    await delete_tag(db, tag_id)
    return {"data": {"message": "Tag deleted successfully"}}


@router.get("/{document_id}")
async def get_doc(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single document with full details."""
    document = await get_document(db, document_id)
    return {"data": DocumentResponse.model_validate(document)}


@router.get("/{document_id}/download")
async def download(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user_or_token)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> StreamingResponse:
    """Download a document as a streaming response.

    Accepts authentication via Bearer header or ?token= query parameter
    so it can be used in <img>, <iframe>, and <a> tags.
    """
    data, document = await download_document(db, storage, document_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{document.original_filename}"',
            "Content-Length": str(document.file_size),
        },
    )


@router.put("/{document_id}")
async def update_doc(
    document_id: uuid.UUID,
    updates: DocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update document metadata."""
    document = await update_document(db, document_id, updates, current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.delete("/{document_id}")
async def delete_doc(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Delete a document (admin only)."""
    await delete_document(db, storage, document_id, current_user)
    return {"data": {"message": "Document deleted successfully"}}


@router.post("/{document_id}/versions", status_code=201)
async def upload_new_version(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
) -> dict:
    """Upload a new version of an existing document."""
    file_data = await file.read()
    settings = request.app.state.settings

    version = await upload_version(
        db=db,
        storage=storage,
        document_id=document_id,
        file_data=file_data,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        user=current_user,
        settings=settings,
    )
    return {"data": DocumentVersionResponse.model_validate(version)}


@router.get("/{document_id}/versions")
async def list_versions(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List all versions of a document."""
    versions = await get_document_versions(db, document_id)
    return {"data": [DocumentVersionResponse.model_validate(v) for v in versions]}


@router.post("/{document_id}/tags")
async def add_tags(
    document_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Add tags to a document."""
    document = await add_tags_to_document(db, document_id, tag_ids, current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.delete("/{document_id}/tags/{tag_id}")
async def remove_tag(
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Remove a tag from a document."""
    document = await remove_tag_from_document(db, document_id, tag_id, current_user)
    return {"data": DocumentResponse.model_validate(document)}
