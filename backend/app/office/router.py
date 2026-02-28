"""FastAPI router for the office module."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
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
