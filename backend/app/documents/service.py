"""Business logic for the documents module."""


import hashlib
import logging
import os
import uuid

from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.documents.models import (
    AuditLog,
    Document,
    DocumentStatus,
    DocumentVersion,
    Folder,
    Tag,
)
from app.documents.schemas import (
    DocumentFilter,
    DocumentUpdate,
    FolderCreate,
    FolderUpdate,
    TagCreate,
    TagUpdate,
)
from app.documents.storage import StorageBackend

# ---------------------------------------------------------------------------
# Allowed MIME types for upload validation
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES: set[str] = {
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/rtf",
    # Spreadsheets
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Presentations
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Images
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/tiff",
    "image/svg+xml",
    "image/bmp",
    "image/heic",
    "image/heif",
    # Text / data
    "text/plain",
    "text/csv",
    "text/xml",
    "application/json",
    "application/xml",
    # Archives
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    # Video
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    # Audio
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/mp4",
}

# Map file extensions to MIME types for octet-stream fallback
_EXTENSION_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "svg": "image/svg+xml",
    "bmp": "image/bmp",
    "heic": "image/heic",
    "heif": "image/heif",
    "txt": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
    "xml": "application/xml",
    "rtf": "application/rtf",
    "zip": "application/zip",
    "gz": "application/gzip",
    "rar": "application/x-rar-compressed",
    "7z": "application/x-7z-compressed",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "weba": "audio/webm",
    "m4a": "audio/mp4",
}


def _resolve_mime_type(content_type: str, filename: str) -> str:
    """Resolve the actual MIME type, falling back to extension-based lookup.

    Browsers sometimes send ``application/octet-stream`` when they can't
    determine the real type.  In that case we infer from the file extension.
    """
    if content_type and content_type != "application/octet-stream":
        return content_type

    ext = _extension_from_filename(filename).lower()
    return _EXTENSION_TO_MIME.get(ext, content_type or "application/octet-stream")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extension_from_filename(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".") if ext else "bin"


async def _create_audit_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    return log


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


async def upload_document(
    db: AsyncSession,
    storage: StorageBackend,
    file_data: bytes,
    filename: str,
    content_type: str,
    user: User,
    folder_id: uuid.UUID | None,
    settings: Settings,
    document_type: str = "other",
    title: str | None = None,
) -> Document:
    """Validate, store, and create a Document with an initial version."""

    # Validate file size (0 = unlimited)
    if settings.max_upload_size > 0 and len(file_data) > settings.max_upload_size:
        logger.warning(
            "Upload rejected: file too large — filename=%s size=%d max=%d user=%s",
            filename, len(file_data), settings.max_upload_size, user.id,
        )
        max_size = settings.max_upload_size
        raise ValidationError(
            f"File size {len(file_data)} exceeds maximum "
            f"allowed size of {max_size} bytes."
        )

    # Resolve MIME type (handles octet-stream fallback via extension)
    content_type = _resolve_mime_type(content_type, filename)

    # Validate MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Upload rejected: disallowed MIME type — filename=%s content_type=%s user=%s",
            filename, content_type, user.id,
        )
        raise ValidationError(
            f"File type '{content_type}' is not allowed. "
            f"Accepted types: PDF, images, spreadsheets, documents, CSV, JSON, "
            f"archives, audio, and video."
        )

    # Validate folder exists if specified
    if folder_id is not None:
        result = await db.execute(select(Folder).where(Folder.id == folder_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Folder", str(folder_id))

    # Compute hash and store file
    file_hash = _compute_sha256(file_data)
    extension = _extension_from_filename(filename)
    storage_path = await storage.save(file_data, extension)

    # Create document record
    document = Document(
        filename=filename,
        original_filename=filename,
        mime_type=content_type,
        file_size=len(file_data),
        file_hash=file_hash,
        storage_path=storage_path,
        folder_id=folder_id,
        document_type=document_type,
        status=DocumentStatus.DRAFT,
        title=title or filename,
        uploaded_by=user.id,
    )
    db.add(document)
    await db.flush()

    # Create initial version
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        filename=filename,
        file_size=len(file_data),
        file_hash=file_hash,
        storage_path=storage_path,
        uploaded_by=user.id,
    )
    db.add(version)

    # Audit log
    await _create_audit_log(
        db,
        user_id=user.id,
        action="upload",
        resource_type="document",
        resource_id=str(document.id),
        details={"filename": filename, "file_size": len(file_data)},
    )

    await db.commit()
    await db.refresh(document)

    logger.info(
        "Document uploaded — id=%s filename=%s mime=%s size=%d user=%s folder=%s",
        document.id, filename, content_type, len(file_data), user.id, folder_id,
    )

    return document


async def list_documents(
    db: AsyncSession,
    filters: DocumentFilter,
    pagination: PaginationParams,
) -> tuple[list[Document], dict]:
    """Return a filtered, paginated list of documents with eager-loaded relationships."""

    query = select(Document).options(
        selectinload(Document.tags),
        selectinload(Document.folder),
    )

    # Exclude trashed documents by default
    query = query.where(Document.is_trashed == False)  # noqa: E712

    # Apply filters
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(
            or_(
                Document.filename.ilike(search_term),
                Document.title.ilike(search_term),
                Document.original_filename.ilike(search_term),
            )
        )

    if filters.folder_id is not None:
        query = query.where(Document.folder_id == filters.folder_id)

    if filters.document_type is not None:
        query = query.where(Document.document_type == filters.document_type)

    if filters.status is not None:
        query = query.where(Document.status == filters.status)

    if filters.uploaded_by is not None:
        query = query.where(Document.uploaded_by == filters.uploaded_by)

    if filters.date_from is not None:
        query = query.where(Document.created_at >= filters.date_from)

    if filters.date_to is not None:
        query = query.where(Document.created_at <= filters.date_to)

    if filters.tag is not None:
        query = query.join(Document.tags).where(Tag.name == filters.tag)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Order and paginate
    sort_column = getattr(Document, filters.sort_by, Document.created_at)
    if filters.sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await db.execute(query)
    documents = list(result.scalars().unique().all())

    meta = build_pagination_meta(total_count, pagination)
    return documents, meta


async def get_document(db: AsyncSession, document_id: uuid.UUID) -> Document:
    """Return a single document with all relationships loaded."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.tags),
            selectinload(Document.folder),
            selectinload(Document.versions),
        )
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document", str(document_id))
    return document


async def update_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    updates: DocumentUpdate,
    user: User,
) -> Document:
    """Partially update document metadata and create an audit log entry."""
    document = await get_document(db, document_id)

    update_data = updates.model_dump(exclude_unset=True)
    changed_fields: dict = {}

    for field, value in update_data.items():
        old_value = getattr(document, field)
        if old_value != value:
            setattr(document, field, value)
            changed_fields[field] = {"old": str(old_value), "new": str(value)}

    if changed_fields:
        await _create_audit_log(
            db,
            user_id=user.id,
            action="update",
            resource_type="document",
            resource_id=str(document_id),
            details=changed_fields,
        )

    await db.commit()
    await db.refresh(document)
    return document


async def delete_document(
    db: AsyncSession,
    storage: StorageBackend,
    document_id: uuid.UUID,
    user: User,
    permanent: bool = False,
) -> None:
    """Delete a document. Soft-deletes by default; permanently deletes if permanent=True."""
    document = await get_document(db, document_id)

    if not permanent:
        # Soft delete: set is_trashed and trashed_at
        document.is_trashed = True
        document.trashed_at = datetime.now(timezone.utc)
        await _create_audit_log(
            db,
            user_id=user.id,
            action="trash",
            resource_type="document",
            resource_id=str(document_id),
            details={"filename": document.filename},
        )
        await db.commit()
        await db.refresh(document)
        return

    # Permanent delete path
    # Collect all storage paths (main + versions)
    paths_to_delete = [document.storage_path]
    for version in document.versions:
        if version.storage_path != document.storage_path:
            paths_to_delete.append(version.storage_path)

    # Explicitly delete ALL related records to avoid FK constraint errors
    from app.collaboration.models import ApprovalWorkflow, Comment
    from app.documents.models import DocumentVersion, document_tags

    await db.execute(delete(Comment).where(Comment.document_id == document_id))
    await db.execute(
        delete(ApprovalWorkflow).where(ApprovalWorkflow.document_id == document_id)
    )
    await db.execute(
        delete(DocumentVersion).where(DocumentVersion.document_id == document_id)
    )
    await db.execute(
        document_tags.delete().where(document_tags.c.document_id == document_id)
    )

    # Nullify SET NULL references
    from app.accounting.models import Expense
    from app.cashbook.models import CashbookEntry
    from app.calendar.models import CalendarEvent
    from sqlalchemy import update

    await db.execute(
        update(Expense).where(Expense.document_id == document_id).values(document_id=None)
    )
    await db.execute(
        update(CashbookEntry).where(CashbookEntry.document_id == document_id).values(document_id=None)
    )
    await db.execute(
        update(CalendarEvent).where(CalendarEvent.document_id == document_id).values(document_id=None)
    )

    # Nullify income reference if the column exists
    try:
        from app.income.models import Income
        await db.execute(
            update(Income).where(Income.document_id == document_id).values(document_id=None)
        )
    except Exception:
        pass

    # Nullify gmail scan result reference if applicable
    try:
        from app.integrations.gmail.models import GmailScanResult
        await db.execute(
            update(GmailScanResult)
            .where(GmailScanResult.matched_document_id == document_id)
            .values(matched_document_id=None)
        )
    except Exception:
        pass

    # Audit log before deletion
    await _create_audit_log(
        db,
        user_id=user.id,
        action="delete",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": document.filename},
    )

    try:
        # Expire the document from session to avoid stale relationship references
        await db.flush()
        await db.execute(delete(Document).where(Document.id == document_id))
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to delete document %s from database", document_id)
        raise

    # Remove files from storage after successful DB commit
    for path in paths_to_delete:
        try:
            await storage.delete(path)
        except Exception:
            logger.warning("Failed to delete storage file: %s", path)


async def download_document(
    db: AsyncSession,
    storage: StorageBackend,
    document_id: uuid.UUID,
) -> tuple[bytes, Document]:
    """Return file bytes and the document record for streaming to the client."""
    document = await get_document(db, document_id)
    data = await storage.read(document.storage_path)
    return data, document


async def search_documents(
    db: AsyncSession,
    query_text: str,
    pagination: PaginationParams,
) -> tuple[list[Document], dict]:
    """Full-text LIKE search across filename, title, and extracted_text."""
    search_term = f"%{query_text}%"

    query = (
        select(Document)
        .options(
            selectinload(Document.tags),
            selectinload(Document.folder),
        )
        .where(
            or_(
                Document.filename.ilike(search_term),
                Document.title.ilike(search_term),
                Document.extracted_text.ilike(search_term),
            )
        )
    )

    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    query = query.order_by(Document.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await db.execute(query)
    documents = list(result.scalars().unique().all())

    meta = build_pagination_meta(total_count, pagination)
    return documents, meta


async def upload_version(
    db: AsyncSession,
    storage: StorageBackend,
    document_id: uuid.UUID,
    file_data: bytes,
    filename: str,
    content_type: str,
    user: User,
    settings: Settings,
) -> DocumentVersion:
    """Upload a new version of an existing document."""

    # Validate file size (0 = unlimited)
    if settings.max_upload_size > 0 and len(file_data) > settings.max_upload_size:
        logger.warning(
            "Version upload rejected: file too large — doc=%s size=%d user=%s",
            document_id, len(file_data), user.id,
        )
        max_size = settings.max_upload_size
        raise ValidationError(
            f"File size {len(file_data)} exceeds maximum "
            f"allowed size of {max_size} bytes."
        )

    # Resolve and validate MIME type
    content_type = _resolve_mime_type(content_type, filename)
    if content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Version upload rejected: disallowed MIME — doc=%s mime=%s user=%s",
            document_id, content_type, user.id,
        )
        raise ValidationError(
            f"File type '{content_type}' is not allowed."
        )

    document = await get_document(db, document_id)

    # Determine next version number
    result = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    # Store file
    file_hash = _compute_sha256(file_data)
    extension = _extension_from_filename(filename)
    storage_path = await storage.save(file_data, extension)

    # Create version record
    version = DocumentVersion(
        document_id=document_id,
        version_number=next_version,
        filename=filename,
        file_size=len(file_data),
        file_hash=file_hash,
        storage_path=storage_path,
        uploaded_by=user.id,
    )
    db.add(version)

    # Update main document to reflect latest version
    document.filename = filename
    document.original_filename = filename
    document.mime_type = content_type
    document.file_size = len(file_data)
    document.file_hash = file_hash
    document.storage_path = storage_path

    # Audit
    await _create_audit_log(
        db,
        user_id=user.id,
        action="upload_version",
        resource_type="document",
        resource_id=str(document_id),
        details={"version_number": next_version, "filename": filename},
    )

    await db.commit()
    await db.refresh(version)

    logger.info(
        "Version uploaded — doc=%s version=%d filename=%s size=%d user=%s",
        document_id, next_version, filename, len(file_data), user.id,
    )

    return version


async def get_document_versions(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> list[DocumentVersion]:
    """Return all versions for a document."""
    # Ensure document exists
    await get_document(db, document_id)

    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------


async def create_folder(
    db: AsyncSession,
    data: FolderCreate,
    user: User,
) -> Folder:
    """Create a new folder."""
    # Check for duplicate name under same parent
    query = select(Folder).where(
        Folder.name == data.name,
        Folder.parent_id == data.parent_id,
    )
    result = await db.execute(query)
    if result.scalar_one_or_none() is not None:
        raise ConflictError(
            f"A folder named '{data.name}' already exists in the specified location."
        )

    # Validate parent folder if specified
    if data.parent_id is not None:
        parent_result = await db.execute(
            select(Folder).where(Folder.id == data.parent_id)
        )
        if parent_result.scalar_one_or_none() is None:
            raise NotFoundError("Folder", str(data.parent_id))

    folder = Folder(
        name=data.name,
        parent_id=data.parent_id,
        description=data.description,
        created_by=user.id,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def get_folder_tree(db: AsyncSession) -> list[Folder]:
    """Return all root-level folders with children eagerly loaded (via model relationship)."""
    result = await db.execute(
        select(Folder)
        .where(Folder.parent_id.is_(None))
        .order_by(Folder.name)
    )
    return list(result.scalars().unique().all())


async def update_folder(
    db: AsyncSession,
    folder_id: uuid.UUID,
    data: FolderUpdate,
    user: User,
) -> Folder:
    """Update a folder's name, parent, or description."""
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if folder is None:
        raise NotFoundError("Folder", str(folder_id))

    update_data = data.model_dump(exclude_unset=True)

    # If renaming, check for duplicate
    new_name = update_data.get("name")
    new_parent = update_data.get("parent_id", folder.parent_id)
    if new_name is not None:
        dup_query = select(Folder).where(
            Folder.name == new_name,
            Folder.parent_id == new_parent,
            Folder.id != folder_id,
        )
        dup_result = await db.execute(dup_query)
        if dup_result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"A folder named '{new_name}' already exists in the specified location."
            )

    for field, value in update_data.items():
        setattr(folder, field, value)

    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(
    db: AsyncSession,
    folder_id: uuid.UUID,
    user: User,
) -> None:
    """Delete a folder (CASCADE will remove child folders via FK)."""
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if folder is None:
        raise NotFoundError("Folder", str(folder_id))

    await _create_audit_log(
        db,
        user_id=user.id,
        action="delete",
        resource_type="folder",
        resource_id=str(folder_id),
        details={"name": folder.name},
    )

    await db.delete(folder)
    await db.commit()


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


async def create_tag(db: AsyncSession, data: TagCreate) -> Tag:
    """Create a new tag."""
    result = await db.execute(select(Tag).where(Tag.name == data.name))
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A tag named '{data.name}' already exists.")

    tag = Tag(name=data.name, color=data.color)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def list_tags(
    db: AsyncSession,
    pagination: PaginationParams | None = None,
) -> list[Tag] | tuple[list[Tag], dict]:
    """Return tags ordered by name, optionally paginated."""
    query = select(Tag).order_by(Tag.name)

    if pagination is None:
        result = await db.execute(query)
        return list(result.scalars().all())

    total = await db.scalar(select(func.count()).select_from(Tag)) or 0
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    tags = list(result.scalars().all())
    return tags, build_pagination_meta(total, pagination)


async def update_tag(
    db: AsyncSession,
    tag_id: uuid.UUID,
    data: TagUpdate,
) -> Tag:
    """Update a tag's name or color."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if tag is None:
        raise NotFoundError("Tag", str(tag_id))

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        dup_result = await db.execute(
            select(Tag).where(Tag.name == update_data["name"], Tag.id != tag_id)
        )
        if dup_result.scalar_one_or_none() is not None:
            raise ConflictError(f"A tag named '{update_data['name']}' already exists.")

    for field, value in update_data.items():
        setattr(tag, field, value)

    await db.commit()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag_id: uuid.UUID) -> None:
    """Delete a tag."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if tag is None:
        raise NotFoundError("Tag", str(tag_id))

    await db.delete(tag)
    await db.commit()


async def add_tags_to_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
    user: User,
) -> Document:
    """Add one or more tags to a document."""
    document = await get_document(db, document_id)

    existing_tag_ids = {t.id for t in document.tags}
    added_names: list[str] = []

    for tag_id in tag_ids:
        if tag_id in existing_tag_ids:
            continue
        result = await db.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if tag is None:
            raise NotFoundError("Tag", str(tag_id))
        document.tags.append(tag)
        added_names.append(tag.name)

    if added_names:
        await _create_audit_log(
            db,
            user_id=user.id,
            action="add_tags",
            resource_type="document",
            resource_id=str(document_id),
            details={"tags_added": added_names},
        )

    await db.commit()
    await db.refresh(document)
    return document


async def remove_tag_from_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    user: User,
) -> Document:
    """Remove a single tag from a document."""
    document = await get_document(db, document_id)

    tag_to_remove = None
    for tag in document.tags:
        if tag.id == tag_id:
            tag_to_remove = tag
            break

    if tag_to_remove is None:
        raise NotFoundError("Tag", str(tag_id))

    document.tags.remove(tag_to_remove)

    await _create_audit_log(
        db,
        user_id=user.id,
        action="remove_tag",
        resource_type="document",
        resource_id=str(document_id),
        details={"tag_removed": tag_to_remove.name},
    )

    await db.commit()
    await db.refresh(document)
    return document


# ---------------------------------------------------------------------------
# Quick Capture (mobile receipt capture)
# ---------------------------------------------------------------------------


async def quick_capture(
    db: AsyncSession,
    storage: StorageBackend,
    file_data: bytes,
    filename: str,
    content_type: str,
    user: User,
    settings: Settings,
) -> tuple[Document, dict | None, object | None, int]:
    """Upload a receipt, extract data with AI, and create an expense in one call."""
    import logging
    import time

    logger = logging.getLogger(__name__)
    start = time.monotonic()

    # Step 1: Upload the receipt document
    document = await upload_document(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=filename,
        content_type=content_type,
        user=user,
        folder_id=None,
        settings=settings,
        document_type="receipt",
        title=None,
    )

    extraction_dict: dict | None = None
    expense = None

    # Step 2: AI extraction (only for supported image/PDF types)
    extractable_types = {
        "image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf",
    }
    if content_type in extractable_types:
        try:
            from app.ai.service import process_document_ai

            _doc, extraction_result = await process_document_ai(
                db, storage, document.id, settings,
            )
            extraction_dict = extraction_result.model_dump(mode="json")
        except Exception:
            logger.warning(
                "Quick capture: AI extraction failed for document %s", document.id, exc_info=True,
            )

    # Step 3: Auto-create expense from extraction results
    if extraction_dict and extraction_dict.get("total_amount"):
        try:
            from app.accounting.service import create_expense_from_document

            expense = await create_expense_from_document(db, document.id, user)
        except Exception:
            logger.warning(
                "Quick capture: expense creation failed for document %s",
                document.id,
                exc_info=True,
            )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return document, extraction_dict, expense, elapsed_ms


# ---------------------------------------------------------------------------
# Star / Trash / Move / List helpers (Google Drive-style features)
# ---------------------------------------------------------------------------


async def star_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    starred: bool,
) -> Document:
    """Toggle star on a document."""
    document = await get_document(db, document_id)
    document.is_starred = starred
    await _create_audit_log(
        db,
        user_id=user_id,
        action="star" if starred else "unstar",
        resource_type="document",
        resource_id=str(document_id),
    )
    await db.commit()
    await db.refresh(document)
    return document


async def trash_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Document:
    """Soft delete -- set is_trashed=True, trashed_at=now."""
    document = await get_document(db, document_id)
    document.is_trashed = True
    document.trashed_at = datetime.now(timezone.utc)
    await _create_audit_log(
        db,
        user_id=user_id,
        action="trash",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": document.filename},
    )
    await db.commit()
    await db.refresh(document)
    return document


async def restore_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Document:
    """Restore from trash -- set is_trashed=False, trashed_at=None."""
    document = await get_document(db, document_id)
    if not document.is_trashed:
        raise ValidationError("Document is not in trash.")
    document.is_trashed = False
    document.trashed_at = None
    await _create_audit_log(
        db,
        user_id=user_id,
        action="restore",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": document.filename},
    )
    await db.commit()
    await db.refresh(document)
    return document


async def empty_trash(
    db: AsyncSession,
    storage: StorageBackend,
    user_id: uuid.UUID,
) -> int:
    """Permanently delete all trashed documents for user. Returns count deleted."""
    # Find all trashed documents for this user
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(
            Document.uploaded_by == user_id,
            Document.is_trashed == True,  # noqa: E712
        )
    )
    trashed_docs = list(result.scalars().unique().all())

    if not trashed_docs:
        return 0

    count = len(trashed_docs)
    storage_paths: list[str] = []

    for doc in trashed_docs:
        storage_paths.append(doc.storage_path)
        for version in doc.versions:
            if version.storage_path != doc.storage_path:
                storage_paths.append(version.storage_path)

    # Collect all document IDs
    doc_ids = [doc.id for doc in trashed_docs]

    # Delete related records
    from app.collaboration.models import ApprovalWorkflow, Comment
    from app.documents.models import DocumentVersion, document_tags

    for doc_id in doc_ids:
        await db.execute(delete(Comment).where(Comment.document_id == doc_id))
        await db.execute(
            delete(ApprovalWorkflow).where(ApprovalWorkflow.document_id == doc_id)
        )
        await db.execute(
            delete(DocumentVersion).where(DocumentVersion.document_id == doc_id)
        )
        await db.execute(
            document_tags.delete().where(document_tags.c.document_id == doc_id)
        )

        # Nullify SET NULL references
        from app.accounting.models import Expense
        from app.cashbook.models import CashbookEntry
        from app.calendar.models import CalendarEvent

        await db.execute(
            update(Expense).where(Expense.document_id == doc_id).values(document_id=None)
        )
        await db.execute(
            update(CashbookEntry)
            .where(CashbookEntry.document_id == doc_id)
            .values(document_id=None)
        )
        await db.execute(
            update(CalendarEvent)
            .where(CalendarEvent.document_id == doc_id)
            .values(document_id=None)
        )

        try:
            from app.income.models import Income

            await db.execute(
                update(Income).where(Income.document_id == doc_id).values(document_id=None)
            )
        except Exception:
            pass

        try:
            from app.integrations.gmail.models import GmailScanResult

            await db.execute(
                update(GmailScanResult)
                .where(GmailScanResult.matched_document_id == doc_id)
                .values(matched_document_id=None)
            )
        except Exception:
            pass

    # Delete all trashed documents
    await db.execute(
        delete(Document).where(
            Document.id.in_(doc_ids),
        )
    )

    await _create_audit_log(
        db,
        user_id=user_id,
        action="empty_trash",
        resource_type="document",
        resource_id="bulk",
        details={"count": count},
    )

    await db.commit()

    # Remove files from storage after successful DB commit
    for path in storage_paths:
        try:
            await storage.delete(path)
        except Exception:
            logger.warning("Failed to delete storage file: %s", path)

    return count


async def move_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    target_folder_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> Document:
    """Move document to a different folder."""
    document = await get_document(db, document_id)

    # Validate target folder if specified
    if target_folder_id is not None:
        result = await db.execute(select(Folder).where(Folder.id == target_folder_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Folder", str(target_folder_id))

    old_folder_id = document.folder_id
    document.folder_id = target_folder_id

    await _create_audit_log(
        db,
        user_id=user_id,
        action="move",
        resource_type="document",
        resource_id=str(document_id),
        details={
            "old_folder_id": str(old_folder_id) if old_folder_id else None,
            "new_folder_id": str(target_folder_id) if target_folder_id else None,
        },
    )

    await db.commit()
    await db.refresh(document)
    return document


async def move_folder(
    db: AsyncSession,
    folder_id: uuid.UUID,
    target_parent_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> Folder:
    """Move folder to a different parent. Prevent circular references."""
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if folder is None:
        raise NotFoundError("Folder", str(folder_id))

    # Prevent moving a folder into itself
    if target_parent_id is not None and target_parent_id == folder_id:
        raise ValidationError("Cannot move a folder into itself.")

    # Prevent circular references: walk up from target_parent_id to root
    if target_parent_id is not None:
        parent_result = await db.execute(
            select(Folder).where(Folder.id == target_parent_id)
        )
        target_parent = parent_result.scalar_one_or_none()
        if target_parent is None:
            raise NotFoundError("Folder", str(target_parent_id))

        # Walk up the tree to detect cycles
        current_id = target_parent_id
        while current_id is not None:
            if current_id == folder_id:
                raise ValidationError(
                    "Cannot move a folder into one of its own descendants."
                )
            ancestor_result = await db.execute(
                select(Folder.parent_id).where(Folder.id == current_id)
            )
            current_id = ancestor_result.scalar_one_or_none()

    old_parent_id = folder.parent_id
    folder.parent_id = target_parent_id

    await _create_audit_log(
        db,
        user_id=user_id,
        action="move",
        resource_type="folder",
        resource_id=str(folder_id),
        details={
            "old_parent_id": str(old_parent_id) if old_parent_id else None,
            "new_parent_id": str(target_parent_id) if target_parent_id else None,
        },
    )

    await db.commit()
    await db.refresh(folder)
    return folder


async def list_starred(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list, int]:
    """List all starred documents and folders for user."""
    # Starred documents
    doc_query = (
        select(Document)
        .options(selectinload(Document.tags), selectinload(Document.folder))
        .where(
            Document.uploaded_by == user_id,
            Document.is_starred == True,  # noqa: E712
            Document.is_trashed == False,  # noqa: E712
        )
        .order_by(Document.updated_at.desc())
    )
    doc_count_query = select(func.count()).select_from(doc_query.subquery())
    doc_total = await db.scalar(doc_count_query) or 0

    doc_result = await db.execute(doc_query.offset(skip).limit(limit))
    documents = list(doc_result.scalars().unique().all())

    # Starred folders
    folder_query = (
        select(Folder)
        .where(
            Folder.created_by == user_id,
            Folder.is_starred == True,  # noqa: E712
            Folder.is_trashed == False,  # noqa: E712
        )
        .order_by(Folder.updated_at.desc())
    )
    folder_result = await db.execute(folder_query)
    folders = list(folder_result.scalars().unique().all())

    # Combine results
    items = [*folders, *documents]
    total = doc_total + len(folders)
    return items, total


async def list_trashed(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Document], int]:
    """List all trashed documents for user."""
    query = (
        select(Document)
        .options(selectinload(Document.tags), selectinload(Document.folder))
        .where(
            Document.uploaded_by == user_id,
            Document.is_trashed == True,  # noqa: E712
        )
        .order_by(Document.trashed_at.desc())
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    result = await db.execute(query.offset(skip).limit(limit))
    documents = list(result.scalars().unique().all())
    return documents, total


async def list_recent(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Document], int]:
    """List recently modified/uploaded documents."""
    query = (
        select(Document)
        .options(selectinload(Document.tags), selectinload(Document.folder))
        .where(
            Document.uploaded_by == user_id,
            Document.is_trashed == False,  # noqa: E712
        )
        .order_by(Document.updated_at.desc())
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    result = await db.execute(query.offset(skip).limit(limit))
    documents = list(result.scalars().unique().all())
    return documents, total


async def get_storage_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Return total storage used: {used_bytes, file_count, folder_count}."""
    file_result = await db.execute(
        select(
            func.coalesce(func.sum(Document.file_size), 0),
            func.count(Document.id),
        ).where(Document.uploaded_by == user_id)
    )
    file_row = file_result.one()
    folder_result = await db.execute(
        select(func.count(Folder.id)).where(Folder.created_by == user_id)
    )
    folder_count = folder_result.scalar_one() or 0
    return {
        "used_bytes": int(file_row[0]),
        "file_count": int(file_row[1]),
        "folder_count": int(folder_count),
    }
