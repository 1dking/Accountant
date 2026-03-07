"""FastAPI router for the documents module."""


import asyncio
import io
import logging
import os
import uuid
from typing import Annotated, Literal

# MIME types that must be served as attachment (not inline) to prevent XSS
_UNSAFE_INLINE_TYPES = {"image/svg+xml", "text/html", "application/xhtml+xml"}

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role
from app.documents.models import DocumentStatus, DocumentType
from app.documents.schemas import (
    BulkDeleteRequest,
    BulkMoveRequest,
    BulkStarRequest,
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
    MoveDocumentRequest,
    MoveFolderRequest,
    QuickCaptureResponse,
    RenameRequest,
    StarRequest,
    StorageUsageResponse,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.documents.service import (
    add_tags_to_document,
    bulk_delete,
    bulk_move,
    bulk_star,
    create_folder,
    create_tag,
    delete_document,
    delete_folder,
    delete_folder_recursive,
    delete_tag,
    download_document,
    empty_trash,
    get_document,
    get_document_versions,
    get_folder_tree,
    get_storage_usage,
    list_documents,
    list_recent,
    list_starred,
    list_tags,
    list_trashed,
    move_document,
    move_folder,
    quick_capture,
    remove_tag_from_document,
    rename_document,
    rename_folder,
    restore_document,
    search_documents,
    star_document,
    star_folder,
    trash_document,
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


async def _resolve_folder_from_path(
    db: AsyncSession,
    user: User,
    relative_path: str,
    parent_folder_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Create intermediate folders from a webkitRelativePath and return the
    final folder ID where the file should be placed.

    ``relative_path`` looks like ``"TopFolder/Sub/file.pdf"``.  We strip the
    filename (last segment) and create ``TopFolder`` then ``Sub`` under
    *parent_folder_id*, returning ``Sub``'s id.
    """
    import posixpath

    parts = posixpath.normpath(relative_path).split("/")
    # Drop the filename (last segment)
    folder_parts = parts[:-1]
    if not folder_parts:
        return parent_folder_id

    current_parent = parent_folder_id
    for folder_name in folder_parts:
        if not folder_name or folder_name == ".":
            continue
        # Try to find existing folder with this name under current parent
        from app.documents.models import Folder
        result = await db.execute(
            select(Folder).where(
                Folder.name == folder_name,
                Folder.parent_id == current_parent,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            current_parent = existing.id
        else:
            new_folder = await create_folder(
                db,
                FolderCreate(
                    name=folder_name,
                    parent_id=current_parent,
                ),
                user,
            )
            current_parent = new_folder.id
    return current_parent


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
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
    folder_id: uuid.UUID | None = Form(None),
    document_type: DocumentType = Form(DocumentType.OTHER),
    title: str | None = Form(None),
    relative_path: str | None = Form(None),
) -> dict:
    """Upload a new document. Auto-triggers AI extraction in background.

    When ``relative_path`` is provided (from webkitdirectory folder uploads),
    intermediate folders are created automatically so the uploaded file ends
    up in the correct nested folder.
    """
    file_data = await file.read()
    settings = request.app.state.settings

    # Resolve folder from relative_path (folder uploads)
    target_folder_id = folder_id
    if relative_path:
        target_folder_id = await _resolve_folder_from_path(
            db, current_user, relative_path, folder_id,
        )

    document = await upload_document(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        user=current_user,
        folder_id=target_folder_id,
        settings=settings,
        document_type=document_type.value,
        title=title,
    )

    # Fire-and-forget AI extraction (asyncio.create_task so it doesn't block response)
    from app.ai.service import EXTRACTABLE_MIME_TYPES

    if document.mime_type in EXTRACTABLE_MIME_TYPES and settings.anthropic_api_key:
        asyncio.create_task(
            _run_ai_extraction(document.id, document.storage_path, settings)
        )

    return {"data": DocumentUploadResponse.model_validate(document)}


@router.post("/quick-capture", status_code=201)
async def quick_capture_endpoint(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    current_user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = None,
    folder_id: uuid.UUID | None = None,
    document_type: DocumentType | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    uploaded_by: uuid.UUID | None = None,
    status: DocumentStatus | None = None,
    sort_by: Literal["created_at", "title", "file_size", "updated_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
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
        sort_by=sort_by,
        sort_order=sort_order,
    )
    documents, meta = await list_documents(db, filters, pagination, user=current_user)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": meta,
    }


@router.get("/search")
async def search(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str = Query(..., min_length=1, description="Search query"),
) -> dict:
    """Search documents by filename, title, or extracted text."""
    documents, meta = await search_documents(db, q, pagination, user=current_user)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": meta,
    }


@router.get("/folders")
async def list_folders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return the folder tree (root folders with nested children)."""
    folders = await get_folder_tree(db, user=current_user)
    return {"data": [FolderTreeResponse.model_validate(f) for f in folders]}


@router.post("/folders", status_code=201)
async def create_folder_endpoint(
    data: FolderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Create a new folder."""
    folder = await create_folder(db, data, current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.put("/folders/{folder_id}")
async def update_folder_endpoint(
    folder_id: uuid.UUID,
    data: FolderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    """Return tags with pagination."""
    tags, meta = await list_tags(db, pagination)
    return {"data": [TagResponse.model_validate(t) for t in tags], "meta": meta}


@router.post("/tags", status_code=201)
async def create_tag_endpoint(
    data: TagCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Create a new tag."""
    tag = await create_tag(db, data)
    return {"data": TagResponse.model_validate(tag)}


@router.put("/tags/{tag_id}")
async def update_tag_endpoint(
    tag_id: uuid.UUID,
    data: TagUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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


@router.get("/starred")
async def list_starred_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List all starred documents and folders for the current user."""
    items, total = await list_starred(db, current_user.id, skip=skip, limit=limit)
    # Serialize: items may be a mix of Document and Folder objects
    data = []
    for item in items:
        if hasattr(item, "mime_type"):
            data.append(DocumentListItem.model_validate(item))
        else:
            data.append(FolderResponse.model_validate(item))
    return {"data": data, "meta": {"total": total, "skip": skip, "limit": limit}}


@router.get("/trash")
async def list_trashed_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List all trashed documents for the current user."""
    documents, total = await list_trashed(db, current_user.id, skip=skip, limit=limit)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


@router.get("/recent")
async def list_recent_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List recently modified/uploaded documents."""
    documents, total = await list_recent(db, current_user.id, skip=skip, limit=limit)
    return {
        "data": [DocumentListItem.model_validate(d) for d in documents],
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


@router.get("/storage-usage")
async def storage_usage_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return storage usage statistics for the current user."""
    usage = await get_storage_usage(db, current_user.id)
    return {"data": StorageUsageResponse(**usage)}


@router.delete("/trash/empty")
async def empty_trash_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Permanently delete all trashed documents for the current user."""
    count = await empty_trash(db, storage, current_user.id)
    return {"data": {"message": f"Permanently deleted {count} documents", "count": count}}


@router.post("/bulk/delete")
async def bulk_delete_endpoint(
    body: BulkDeleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Bulk delete documents and folders (admin only)."""
    result = await bulk_delete(
        db, storage, body.document_ids, body.folder_ids, current_user
    )
    return {"data": result}


@router.post("/bulk/move")
async def bulk_move_endpoint(
    body: BulkMoveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Bulk move documents and folders."""
    result = await bulk_move(
        db, body.document_ids, body.folder_ids, body.target_folder_id, current_user.id, user=current_user
    )
    return {"data": result}


@router.post("/bulk/star")
async def bulk_star_endpoint(
    body: BulkStarRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Bulk star/unstar documents and folders."""
    result = await bulk_star(
        db, body.document_ids, body.folder_ids, body.starred, current_user.id, user=current_user
    )
    return {"data": result}


@router.post("/folders/{folder_id}/star")
async def star_folder_endpoint(
    folder_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: StarRequest | None = None,
) -> dict:
    """Toggle star on a folder."""
    starred = body.starred if body is not None else True
    folder = await star_folder(db, folder_id, current_user.id, starred, user=current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.post("/folders/{folder_id}/delete-recursive")
async def delete_folder_recursive_endpoint(
    folder_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Recursively delete a folder and all its contents (admin only)."""
    count = await delete_folder_recursive(db, storage, folder_id, current_user)
    return {"data": {"message": f"Folder and {count} documents deleted", "documents_deleted": count}}


@router.put("/{document_id}/rename")
async def rename_document_endpoint(
    document_id: uuid.UUID,
    body: RenameRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Rename a document."""
    document = await rename_document(db, document_id, body.name, current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.put("/folders/{folder_id}/rename")
async def rename_folder_endpoint(
    folder_id: uuid.UUID,
    body: RenameRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Rename a folder."""
    folder = await rename_folder(db, folder_id, body.name, current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.get("/{document_id}")
async def get_doc(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single document with full details."""
    document = await get_document(db, document_id, user=current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.get("/{document_id}/download")
async def download(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_token)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
):
    """Download a document as a streaming response.

    Accepts authentication via Bearer header or ?token= query parameter
    so it can be used in <img>, <iframe>, and <a> tags.

    Uses FileResponse for local storage to stream from disk without
    loading the entire file into memory.
    """
    document = await get_document(db, document_id, user=current_user)

    # Sanitize filename for Content-Disposition header
    safe_filename = os.path.basename(document.original_filename).replace('"', '_')
    # Force download for potentially dangerous MIME types
    disposition = "attachment" if document.mime_type in _UNSAFE_INLINE_TYPES else "inline"

    # Stream from disk if local storage (avoids loading into memory)
    if hasattr(storage, "get_full_path"):
        file_path = storage.get_full_path(document.storage_path)
        return FileResponse(
            path=str(file_path),
            media_type=document.mime_type,
            filename=safe_filename,
            headers={"Content-Disposition": f'{disposition}; filename="{safe_filename}"'},
        )

    # Fallback for non-local storage backends
    data, document = await download_document(db, storage, document_id, user=current_user)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
            "Content-Length": str(document.file_size),
        },
    )


@router.put("/{document_id}")
async def update_doc(
    document_id: uuid.UUID,
    updates: DocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Update document metadata."""
    document = await update_document(db, document_id, updates, current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.delete("/{document_id}")
async def delete_doc(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    permanent: bool = Query(False, description="Permanently delete instead of trash"),
) -> dict:
    """Delete a document (soft-delete by default, permanent if ?permanent=true)."""
    await delete_document(db, storage, document_id, current_user, permanent=permanent)
    return {"data": {"message": "Document deleted successfully"}}


@router.post("/{document_id}/star")
async def star_document_endpoint(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: StarRequest | None = None,
) -> dict:
    """Toggle star on a document."""
    starred = body.starred if body is not None else True
    document = await star_document(db, document_id, current_user.id, starred, user=current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.post("/{document_id}/trash")
async def trash_document_endpoint(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Soft-delete a document (move to trash)."""
    document = await trash_document(db, document_id, current_user.id, user=current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.post("/{document_id}/restore")
async def restore_document_endpoint(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Restore a document from trash."""
    document = await restore_document(db, document_id, current_user.id, user=current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.post("/{document_id}/move")
async def move_document_endpoint(
    document_id: uuid.UUID,
    body: MoveDocumentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Move a document to a different folder."""
    document = await move_document(db, document_id, body.folder_id, current_user.id, user=current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.post("/folders/{folder_id}/move")
async def move_folder_endpoint(
    folder_id: uuid.UUID,
    body: MoveFolderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Move a folder to a different parent folder."""
    folder = await move_folder(db, folder_id, body.parent_id, current_user.id, user=current_user)
    return {"data": FolderResponse.model_validate(folder)}


@router.get("/{document_id}/stream")
async def stream_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_token)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> StreamingResponse:
    """Stream a document with HTTP Range header support for video playback.

    Supports partial content requests (Range: bytes=start-end) and returns
    206 Partial Content with the appropriate Content-Range header.

    Uses file-based streaming for local storage to avoid loading entire
    files into memory (important for large video files).
    """
    document = await get_document(db, document_id, user=current_user)

    # Sanitize filename for Content-Disposition header
    safe_filename = os.path.basename(document.original_filename).replace('"', '_')
    # Force download for potentially dangerous MIME types
    disposition = "attachment" if document.mime_type in _UNSAFE_INLINE_TYPES else "inline"

    # Use file-based streaming for local storage
    if hasattr(storage, "get_full_path"):
        file_path = storage.get_full_path(document.storage_path)
        file_size = file_path.stat().st_size

        range_header = request.headers.get("range")
        if range_header:
            range_str = range_header.strip().lower()
            if range_str.startswith("bytes="):
                range_str = range_str[6:]
                parts = range_str.split("-", 1)
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
                start = max(0, start)
                end = min(end, file_size - 1)
                content_length = end - start + 1

                async def range_generator():
                    chunk_size = 64 * 1024  # 64KB chunks
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = content_length
                        while remaining > 0:
                            read_size = min(chunk_size, remaining)
                            chunk = f.read(read_size)
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk

                return StreamingResponse(
                    range_generator(),
                    status_code=206,
                    media_type=document.mime_type,
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(content_length),
                        "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
                    },
                )

        # No Range header — stream full file in chunks
        async def file_generator():
            chunk_size = 64 * 1024
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        return StreamingResponse(
            file_generator(),
            media_type=document.mime_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
            },
        )

    # Fallback: load into memory for non-local storage backends
    data, document = await download_document(db, storage, document_id, user=current_user)
    file_size = len(data)

    range_header = request.headers.get("range")
    if range_header:
        range_str = range_header.strip().lower()
        if range_str.startswith("bytes="):
            range_str = range_str[6:]
            parts = range_str.split("-", 1)
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
            start = max(0, start)
            end = min(end, file_size - 1)
            content_length = end - start + 1

            return StreamingResponse(
                io.BytesIO(data[start : end + 1]),
                status_code=206,
                media_type=document.mime_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(content_length),
                    "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
                },
            )

    return StreamingResponse(
        io.BytesIO(data),
        media_type=document.mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
        },
    )


@router.post("/{document_id}/versions", status_code=201)
async def upload_new_version(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List all versions of a document."""
    versions = await get_document_versions(db, document_id, user=current_user)
    return {"data": [DocumentVersionResponse.model_validate(v) for v in versions]}


@router.post("/{document_id}/tags")
async def add_tags(
    document_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Add tags to a document."""
    document = await add_tags_to_document(db, document_id, tag_ids, current_user)
    return {"data": DocumentResponse.model_validate(document)}


@router.delete("/{document_id}/tags/{tag_id}")
async def remove_tag(
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    """Remove a tag from a document."""
    document = await remove_tag_from_document(db, document_id, tag_id, current_user)
    return {"data": DocumentResponse.model_validate(document)}
