"""FastAPI router for the office module."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.office import service
from app.office.schemas import (
    CollaboratorResponse,
    OfficeDocCreate,
    OfficeDocListItem,
    OfficeDocResponse,
    OfficeDocUpdate,
    ShareRequest,
    StarRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_document(
    data: OfficeDocCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Create a new office document."""
    doc = await service.create_document(db, current_user, data)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.get("/")
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    doc_type: str | None = None,
    folder_id: uuid.UUID | None = None,
    view: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """List documents with filtering.

    Query params:
    - doc_type: document, spreadsheet, presentation
    - folder_id: filter by folder
    - view: owned | shared | starred | trashed | recent
    - search: search title and content
    - skip / limit: pagination
    """
    # Derive boolean flags from the view parameter
    owned_by_me = True
    shared_with_me = False
    starred_only = False
    trashed = False

    if view == "shared":
        owned_by_me = False
        shared_with_me = True
    elif view == "starred":
        starred_only = True
        owned_by_me = True
        shared_with_me = True
    elif view == "trashed":
        trashed = True
    elif view == "recent":
        owned_by_me = True
        shared_with_me = True

    documents, total_count = await service.list_documents(
        db,
        user_id=current_user.id,
        doc_type=doc_type,
        folder_id=folder_id,
        starred_only=starred_only,
        trashed=trashed,
        owned_by_me=owned_by_me,
        shared_with_me=shared_with_me,
        search=search,
        skip=skip,
        limit=limit,
    )

    return {
        "data": [OfficeDocListItem.model_validate(d) for d in documents],
        "meta": {
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
        },
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single document with collaborators."""
    doc = await service.get_document(db, doc_id, current_user)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.put("/{doc_id}")
async def update_document(
    doc_id: uuid.UUID,
    data: OfficeDocUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Update document metadata."""
    doc = await service.update_document(db, doc_id, current_user, data)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Soft delete a document (move to trash)."""
    await service.delete_document(db, doc_id, current_user)
    return {"data": {"message": "Document moved to trash"}}


# ---------------------------------------------------------------------------
# Yjs state (used by Hocuspocus server)
# ---------------------------------------------------------------------------


@router.get("/{doc_id}/state")
async def get_state(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Return the raw Yjs document state as binary."""
    state = await service.get_yjs_state(db, doc_id)
    if state is None:
        return Response(content=b"", media_type="application/octet-stream")
    return Response(content=state, media_type="application/octet-stream")


@router.put("/{doc_id}/state")
async def save_state(
    doc_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Save the raw Yjs document state from binary request body."""
    body = await request.body()
    await service.save_yjs_state(db, doc_id, body)
    return {"data": {"status": "saved"}}


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


@router.post("/{doc_id}/share", status_code=201)
async def share_document(
    doc_id: uuid.UUID,
    data: ShareRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Share a document with another user."""
    access = await service.share_document(
        db, doc_id, current_user, data.user_id, data.permission
    )
    return {"data": CollaboratorResponse.model_validate(access)}


@router.delete("/{doc_id}/share/{user_id}")
async def unshare_document(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Remove a user's access to a document."""
    await service.unshare_document(db, doc_id, current_user, user_id)
    return {"data": {"message": "Access removed"}}


@router.get("/{doc_id}/collaborators")
async def list_collaborators(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List all collaborators for a document."""
    collaborators = await service.list_collaborators(db, doc_id)
    return {"data": [CollaboratorResponse.model_validate(c) for c in collaborators]}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@router.post("/{doc_id}/duplicate", status_code=201)
async def duplicate_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Duplicate a document."""
    doc = await service.duplicate_document(db, doc_id, current_user)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.post("/{doc_id}/star")
async def star_document(
    doc_id: uuid.UUID,
    data: StarRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Star or unstar a document."""
    doc = await service.star_document(db, doc_id, current_user.id, data.starred)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.post("/{doc_id}/trash")
async def trash_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Move a document to trash."""
    doc = await service.trash_document(db, doc_id, current_user.id)
    return {"data": OfficeDocResponse.model_validate(doc)}


@router.post("/{doc_id}/restore")
async def restore_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Restore a trashed document."""
    doc = await service.restore_document(db, doc_id, current_user.id)
    return {"data": OfficeDocResponse.model_validate(doc)}


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


@router.get("/{doc_id}/export/pptx")
async def export_pptx(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Export a presentation to PPTX."""
    from app.office.export_service import export_pptx as do_export

    doc = await service.get_document(db, doc_id, current_user)
    data = do_export(doc.title, doc.content_json)
    filename = f"{doc.title or 'presentation'}.pptx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/export/xlsx")
async def export_xlsx(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Export a spreadsheet to XLSX."""
    from app.office.export_service import export_xlsx as do_export

    doc = await service.get_document(db, doc_id, current_user)
    data = do_export(doc.title, doc.content_json)
    filename = f"{doc.title or 'spreadsheet'}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/export/docx")
async def export_docx(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Export a document to DOCX."""
    from app.office.export_service import export_docx as do_export

    doc = await service.get_document(db, doc_id, current_user)
    data = do_export(doc.title, doc.content_json)
    filename = f"{doc.title or 'document'}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/export/pdf")
async def export_pdf(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Export any document type to printable HTML (for browser PDF)."""
    from app.office.export_service import export_pdf_html

    doc = await service.get_document(db, doc_id, current_user)
    html = export_pdf_html(doc.title, doc.content_json, doc.doc_type.value)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/{doc_id}/export/csv")
async def export_csv(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    sheet: int = 0,
) -> Response:
    """Export a spreadsheet sheet to CSV."""
    from app.office.export_service import export_csv as do_export

    doc = await service.get_document(db, doc_id, current_user)
    csv_str = do_export(doc.content_json, sheet)
    filename = f"{doc.title or 'spreadsheet'}.csv"
    return Response(
        content=csv_str,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{doc_id}/import")
async def import_file(
    doc_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Import a file (PPTX, XLSX, DOCX) into an existing document.

    The file type is detected from the filename extension.
    The document's content_json is replaced with the imported content.
    """
    from app.office.export_service import import_docx, import_pptx, import_xlsx
    from app.office.schemas import OfficeDocUpdate

    file_bytes = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pptx"):
        content_json = import_pptx(file_bytes)
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        content_json = import_xlsx(file_bytes)
    elif filename.endswith(".docx"):
        content_json = import_docx(file_bytes)
    else:
        return {"error": {"code": "UNSUPPORTED_FORMAT", "message": "Supported formats: .pptx, .xlsx, .docx"}}

    update = OfficeDocUpdate(content_json=content_json)
    doc = await service.update_document(db, doc_id, current_user, update)
    return {"data": OfficeDocResponse.model_validate(doc)}
