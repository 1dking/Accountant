"""Business logic for the documents module."""


import hashlib
import os
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/csv",
    "application/json",
}


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

    # Validate file size
    if len(file_data) > settings.max_upload_size:
        raise ValidationError(
            f"File size {len(file_data)} exceeds maximum allowed size of {settings.max_upload_size} bytes."
        )

    # Validate MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"File type '{content_type}' is not allowed. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
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
    query = query.order_by(Document.created_at.desc())
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
) -> None:
    """Delete a document, its versions, and the underlying storage files."""
    document = await get_document(db, document_id)

    # Collect all storage paths (main + versions)
    paths_to_delete = [document.storage_path]
    for version in document.versions:
        if version.storage_path != document.storage_path:
            paths_to_delete.append(version.storage_path)

    # Audit log before deletion
    await _create_audit_log(
        db,
        user_id=user.id,
        action="delete",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": document.filename},
    )

    await db.delete(document)
    await db.commit()

    # Remove files from storage after successful DB commit
    for path in paths_to_delete:
        await storage.delete(path)


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

    # Validate
    if len(file_data) > settings.max_upload_size:
        raise ValidationError(
            f"File size {len(file_data)} exceeds maximum allowed size of {settings.max_upload_size} bytes."
        )
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(f"File type '{content_type}' is not allowed.")

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


async def list_tags(db: AsyncSession) -> list[Tag]:
    """Return all tags ordered by name."""
    result = await db.execute(select(Tag).order_by(Tag.name))
    return list(result.scalars().all())


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
