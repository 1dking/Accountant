"""Business logic for the office module."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.collaboration.service import log_activity
from app.core.exceptions import ForbiddenError, NotFoundError
from app.office.models import (
    DocType,
    OfficeDocument,
    OfficeDocumentAccess,
    Permission,
)
from app.office.schemas import OfficeDocCreate, OfficeDocUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------


async def _check_access(
    db: AsyncSession,
    doc: OfficeDocument,
    user: User,
    require_owner: bool = False,
) -> None:
    """Raise ForbiddenError if user has no access to the document.

    If require_owner is True, only the document creator is allowed.
    """
    if doc.created_by == user.id:
        return

    if require_owner:
        raise ForbiddenError("Only the document owner can perform this action.")

    result = await db.execute(
        select(OfficeDocumentAccess).where(
            OfficeDocumentAccess.document_id == doc.id,
            OfficeDocumentAccess.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ForbiddenError("You do not have access to this document.")


async def _get_document_or_404(
    db: AsyncSession,
    doc_id: uuid.UUID,
) -> OfficeDocument:
    """Fetch a document by ID or raise NotFoundError."""
    result = await db.execute(
        select(OfficeDocument)
        .options(selectinload(OfficeDocument.access_list))
        .where(OfficeDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError("OfficeDocument", str(doc_id))
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_document(
    db: AsyncSession,
    user: User,
    data: OfficeDocCreate,
) -> OfficeDocument:
    """Create a new office document."""
    doc = OfficeDocument(
        title=data.title,
        doc_type=DocType(data.doc_type),
        created_by=user.id,
        folder_id=data.folder_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Log activity
    await log_activity(
        db,
        user_id=user.id,
        action="office_document_created",
        resource_type="office_document",
        resource_id=str(doc.id),
        details={"title": doc.title, "doc_type": doc.doc_type.value},
    )

    # Re-fetch with relationships loaded
    return await _get_document_or_404(db, doc.id)


async def get_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
) -> OfficeDocument:
    """Get a single document, checking access and updating last_accessed_at."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    # Update last accessed timestamp
    doc.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)

    return doc


async def list_documents(
    db: AsyncSession,
    user_id: uuid.UUID,
    doc_type: str | None = None,
    folder_id: uuid.UUID | None = None,
    starred_only: bool = False,
    trashed: bool = False,
    owned_by_me: bool = True,
    shared_with_me: bool = False,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[OfficeDocument], int]:
    """List documents with filtering and pagination."""
    query = select(OfficeDocument)

    # Ownership / sharing filter
    if owned_by_me and not shared_with_me:
        query = query.where(OfficeDocument.created_by == user_id)
    elif shared_with_me and not owned_by_me:
        shared_ids_query = select(OfficeDocumentAccess.document_id).where(
            OfficeDocumentAccess.user_id == user_id
        )
        query = query.where(OfficeDocument.id.in_(shared_ids_query))
    elif owned_by_me and shared_with_me:
        shared_ids_query = select(OfficeDocumentAccess.document_id).where(
            OfficeDocumentAccess.user_id == user_id
        )
        query = query.where(
            or_(
                OfficeDocument.created_by == user_id,
                OfficeDocument.id.in_(shared_ids_query),
            )
        )

    # Trash filter
    if trashed:
        query = query.where(OfficeDocument.is_trashed.is_(True))
    else:
        query = query.where(OfficeDocument.is_trashed.is_(False))

    # Doc type filter
    if doc_type is not None:
        query = query.where(OfficeDocument.doc_type == DocType(doc_type))

    # Folder filter
    if folder_id is not None:
        query = query.where(OfficeDocument.folder_id == folder_id)

    # Starred filter
    if starred_only:
        query = query.where(OfficeDocument.is_starred.is_(True))

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                OfficeDocument.title.ilike(search_term),
                OfficeDocument.content_text.ilike(search_term),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Order and paginate
    query = query.order_by(OfficeDocument.updated_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    documents = list(result.scalars().unique().all())

    return documents, total_count


async def update_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
    data: OfficeDocUpdate,
) -> OfficeDocument:
    """Update document metadata."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)

    await db.commit()
    await db.refresh(doc)

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_updated",
        resource_type="office_document",
        resource_id=str(doc.id),
        details={"updated_fields": list(update_data.keys())},
    )

    return await _get_document_or_404(db, doc.id)


async def delete_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
) -> None:
    """Soft delete a document (move to trash)."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    doc.is_trashed = True
    doc.trashed_at = datetime.now(timezone.utc)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_trashed",
        resource_type="office_document",
        resource_id=str(doc.id),
    )


async def duplicate_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
) -> OfficeDocument:
    """Duplicate a document. The copy is owned by the requesting user."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    new_doc = OfficeDocument(
        title=f"{doc.title} (Copy)",
        doc_type=doc.doc_type,
        created_by=user.id,
        folder_id=doc.folder_id,
        yjs_state=doc.yjs_state,
        content_text=doc.content_text,
        content_json=doc.content_json,
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_duplicated",
        resource_type="office_document",
        resource_id=str(new_doc.id),
        details={"source_document_id": str(doc_id)},
    )

    return await _get_document_or_404(db, new_doc.id)


# ---------------------------------------------------------------------------
# Yjs state (for Hocuspocus)
# ---------------------------------------------------------------------------


async def get_yjs_state(
    db: AsyncSession,
    doc_id: uuid.UUID,
) -> bytes | None:
    """Return the raw Yjs document state bytes."""
    result = await db.execute(
        select(OfficeDocument.yjs_state).where(OfficeDocument.id == doc_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("OfficeDocument", str(doc_id))
    return row[0]


async def save_yjs_state(
    db: AsyncSession,
    doc_id: uuid.UUID,
    state: bytes,
) -> None:
    """Persist the Yjs document state and extract plain text if possible."""
    result = await db.execute(
        select(OfficeDocument).where(OfficeDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError("OfficeDocument", str(doc_id))

    doc.yjs_state = state

    # Attempt plain-text extraction from the Yjs state for search indexing.
    # This is best-effort -- if the yjs library is not installed or the
    # state cannot be decoded, we silently skip extraction.
    try:
        import y_py as Y  # type: ignore[import-untyped]

        ydoc = Y.YDoc()
        Y.apply_update(ydoc, state)
        text = ydoc.get_text("default")
        doc.content_text = str(text)
    except Exception:
        # y_py not installed or state not decodable -- skip extraction
        pass

    await db.commit()


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


async def share_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
    target_user_id: uuid.UUID,
    permission: str = "edit",
) -> OfficeDocumentAccess:
    """Share a document with another user. Only the owner can share.

    Performs an upsert: updates permission if already shared.
    """
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user, require_owner=True)

    # Check if access already exists
    result = await db.execute(
        select(OfficeDocumentAccess).where(
            OfficeDocumentAccess.document_id == doc_id,
            OfficeDocumentAccess.user_id == target_user_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.permission = Permission(permission)
        existing.granted_by = user.id
        await db.commit()
        await db.refresh(existing)
        access = existing
    else:
        access = OfficeDocumentAccess(
            document_id=doc_id,
            user_id=target_user_id,
            permission=Permission(permission),
            granted_by=user.id,
        )
        db.add(access)
        await db.commit()
        await db.refresh(access)

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_shared",
        resource_type="office_document",
        resource_id=str(doc_id),
        details={
            "target_user_id": str(target_user_id),
            "permission": permission,
        },
    )

    return access


async def unshare_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
    target_user_id: uuid.UUID,
) -> None:
    """Remove a user's access to a document. Only the owner can unshare."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user, require_owner=True)

    result = await db.execute(
        select(OfficeDocumentAccess).where(
            OfficeDocumentAccess.document_id == doc_id,
            OfficeDocumentAccess.user_id == target_user_id,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        raise NotFoundError("OfficeDocumentAccess", str(target_user_id))

    await db.delete(access)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_unshared",
        resource_type="office_document",
        resource_id=str(doc_id),
        details={"target_user_id": str(target_user_id)},
    )


async def list_collaborators(
    db: AsyncSession,
    doc_id: uuid.UUID,
) -> list[OfficeDocumentAccess]:
    """Return all access entries for a document."""
    result = await db.execute(
        select(OfficeDocumentAccess).where(
            OfficeDocumentAccess.document_id == doc_id
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Star / Trash / Restore
# ---------------------------------------------------------------------------


async def star_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    starred: bool,
) -> OfficeDocument:
    """Star or unstar a document."""
    doc = await _get_document_or_404(db, doc_id)

    # User must be owner or have access
    if doc.created_by != user_id:
        result = await db.execute(
            select(OfficeDocumentAccess).where(
                OfficeDocumentAccess.document_id == doc_id,
                OfficeDocumentAccess.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ForbiddenError("You do not have access to this document.")

    doc.is_starred = starred
    await db.commit()
    await db.refresh(doc)
    return doc


async def trash_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OfficeDocument:
    """Move a document to trash."""
    doc = await _get_document_or_404(db, doc_id)

    if doc.created_by != user_id:
        raise ForbiddenError("Only the document owner can trash this document.")

    doc.is_trashed = True
    doc.trashed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)

    await log_activity(
        db,
        user_id=user_id,
        action="office_document_trashed",
        resource_type="office_document",
        resource_id=str(doc_id),
    )

    return doc


async def restore_document(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OfficeDocument:
    """Restore a trashed document."""
    doc = await _get_document_or_404(db, doc_id)

    if doc.created_by != user_id:
        raise ForbiddenError("Only the document owner can restore this document.")

    doc.is_trashed = False
    doc.trashed_at = None
    await db.commit()
    await db.refresh(doc)

    await log_activity(
        db,
        user_id=user_id,
        action="office_document_restored",
        resource_type="office_document",
        resource_id=str(doc_id),
    )

    return doc
