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
from app.notifications.service import create_notification
from app.office.models import (
    DocType,
    OfficeDocument,
    OfficeDocumentAccess,
    OfficeDocumentComment,
    OfficeDocumentVersion,
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
        content_json=data.content_json,
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

    if "content_json" in update_data:
        snapshotted = await _snapshot_version_if_due(db, doc, user)
        if snapshotted:
            await _notify_collaborators_of_edit(db, doc, user)

    return await _get_document_or_404(db, doc.id)


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

VERSION_AUTOSAVE_INTERVAL_MINUTES = 15


async def _next_version_number(db: AsyncSession, doc_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(OfficeDocumentVersion.version_number)).where(
            OfficeDocumentVersion.document_id == doc_id
        )
    )
    current_max = result.scalar()
    return (current_max or 0) + 1


async def _snapshot_version_if_due(
    db: AsyncSession, doc: OfficeDocument, user: User
) -> bool:
    """Auto-checkpoint during editing, throttled so autosave (every ~2s)
    doesn't create a version per keystroke — only when the latest
    snapshot is missing or older than VERSION_AUTOSAVE_INTERVAL_MINUTES.

    Returns True if a snapshot was actually taken (used to piggyback the
    "someone edited this doc" notification on the same throttle, rather
    than firing it on every autosave tick too).
    """
    result = await db.execute(
        select(OfficeDocumentVersion.created_at)
        .where(OfficeDocumentVersion.document_id == doc.id)
        .order_by(OfficeDocumentVersion.version_number.desc())
        .limit(1)
    )
    last_created_at = result.scalar()
    if last_created_at is not None:
        age = datetime.now(timezone.utc) - last_created_at.replace(tzinfo=timezone.utc)
        if age.total_seconds() < VERSION_AUTOSAVE_INTERVAL_MINUTES * 60:
            return False
    await create_version(db, doc.id, user)
    return True


async def _notify_collaborators_of_edit(
    db: AsyncSession, doc: OfficeDocument, editor: User
) -> None:
    """Notify the owner and every other collaborator (excluding the editor)
    that the document changed. Piggybacks on the version-snapshot throttle
    so this fires at most once per VERSION_AUTOSAVE_INTERVAL_MINUTES, not
    once per autosave tick.
    """
    recipients: set[uuid.UUID] = {doc.created_by}
    result = await db.execute(
        select(OfficeDocumentAccess.user_id).where(
            OfficeDocumentAccess.document_id == doc.id
        )
    )
    recipients.update(row[0] for row in result.all())
    recipients.discard(editor.id)

    for recipient_id in recipients:
        await create_notification(
            db,
            user_id=recipient_id,
            type="office_document_edited",
            title="Document updated",
            message=f'{editor.full_name} edited "{doc.title}".',
            resource_type="office_document",
            resource_id=str(doc.id),
            link_path=f"/docs/{doc.id}",
        )


async def create_version(
    db: AsyncSession, doc_id: uuid.UUID, user: User
) -> OfficeDocumentVersion:
    """Snapshot the document's current content_json as a new version."""
    doc = await _get_document_or_404(db, doc_id)
    version_number = await _next_version_number(db, doc_id)
    version = OfficeDocumentVersion(
        document_id=doc_id,
        version_number=version_number,
        content_json=doc.content_json,
        title=doc.title,
        created_by=user.id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(
    db: AsyncSession, doc_id: uuid.UUID, user: User
) -> list[OfficeDocumentVersion]:
    """Return all version snapshots for a document, newest first."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    result = await db.execute(
        select(OfficeDocumentVersion)
        .where(OfficeDocumentVersion.document_id == doc_id)
        .order_by(OfficeDocumentVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def restore_version(
    db: AsyncSession, doc_id: uuid.UUID, version_id: uuid.UUID, user: User
) -> OfficeDocument:
    """Restore a document to a prior version's content.

    Snapshots the current (about-to-be-overwritten) content as a new
    version first, so restoring is never destructive — you can always
    restore forward again.
    """
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    result = await db.execute(
        select(OfficeDocumentVersion).where(
            OfficeDocumentVersion.id == version_id,
            OfficeDocumentVersion.document_id == doc_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise NotFoundError("OfficeDocumentVersion", str(version_id))

    await create_version(db, doc_id, user)

    doc.content_json = version.content_json
    await db.commit()
    await db.refresh(doc)

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_version_restored",
        resource_type="office_document",
        resource_id=str(doc_id),
        details={"restored_version_number": version.version_number},
    )

    return doc


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

    await create_notification(
        db,
        user_id=target_user_id,
        type="office_document_shared",
        title="Document shared with you",
        message=f'{user.full_name} shared "{doc.title}" with you.',
        resource_type="office_document",
        resource_id=str(doc_id),
        link_path=f"/docs/{doc_id}",
    )

    # Attach the sharee's display info — CollaboratorResponse reads these
    # via from_attributes; ShareDialog shows a "?" placeholder without them.
    target_user = await db.get(User, target_user_id)
    access.user_name = target_user.full_name if target_user else ""
    access.user_email = target_user.email if target_user else ""

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
    """Return all access entries for a document, with each sharee's name
    and email attached — CollaboratorResponse reads these via
    from_attributes; ShareDialog shows a "?" placeholder without them.
    """
    result = await db.execute(
        select(OfficeDocumentAccess, User)
        .join(User, User.id == OfficeDocumentAccess.user_id)
        .where(OfficeDocumentAccess.document_id == doc_id)
    )
    entries = []
    for access, sharee in result.all():
        access.user_name = sharee.full_name
        access.user_email = sharee.email
        entries.append(access)
    return entries


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


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


async def create_comment(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
    content: str,
    parent_id: uuid.UUID | None = None,
    mentioned_user_ids: list[uuid.UUID] | None = None,
) -> OfficeDocumentComment:
    """Create a comment on a document, mirroring
    collaboration/service.py:create_comment.

    Side-effects: notifies the document owner (if someone else commented)
    and every explicitly @mentioned user.
    """
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    if parent_id is not None:
        parent_result = await db.execute(
            select(OfficeDocumentComment).where(
                OfficeDocumentComment.id == parent_id,
                OfficeDocumentComment.document_id == doc_id,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise NotFoundError("OfficeDocumentComment", str(parent_id))

    comment = OfficeDocumentComment(
        document_id=doc_id,
        user_id=user.id,
        parent_id=parent_id,
        content=content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_commented",
        resource_type="office_document",
        resource_id=str(doc_id),
        details={"comment_id": str(comment.id)},
    )

    # Notify the owner, then any distinct @mentioned users -- never double
    # notify the same person, and never notify the commenter themselves.
    notified: set[uuid.UUID] = {user.id}
    if doc.created_by not in notified:
        await create_notification(
            db,
            user_id=doc.created_by,
            type="office_document_comment",
            title="New comment",
            message=f'{user.full_name} commented on "{doc.title}".',
            resource_type="office_document",
            resource_id=str(doc_id),
            link_path=f"/docs/{doc_id}",
        )
        notified.add(doc.created_by)

    for mentioned_id in mentioned_user_ids or []:
        if mentioned_id in notified:
            continue
        await create_notification(
            db,
            user_id=mentioned_id,
            type="office_document_mention",
            title="You were mentioned",
            message=f'{user.full_name} mentioned you in a comment on "{doc.title}".',
            resource_type="office_document",
            resource_id=str(doc_id),
            link_path=f"/docs/{doc_id}",
        )
        notified.add(mentioned_id)

    comment.user_name = user.full_name
    comment.user_email = user.email
    return comment


async def list_comments(
    db: AsyncSession,
    doc_id: uuid.UUID,
    user: User,
) -> list[OfficeDocumentComment]:
    """Return a flat list of all comments for a document, oldest first, with
    each author's name/email attached. The frontend builds the reply tree
    from parent_id."""
    doc = await _get_document_or_404(db, doc_id)
    await _check_access(db, doc, user)

    result = await db.execute(
        select(OfficeDocumentComment, User.full_name, User.email)
        .join(User, User.id == OfficeDocumentComment.user_id)
        .where(OfficeDocumentComment.document_id == doc_id)
        .order_by(OfficeDocumentComment.created_at.asc())
    )
    comments = []
    for comment, full_name, email in result.all():
        comment.user_name = full_name
        comment.user_email = email
        comments.append(comment)
    return comments


async def update_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    user: User,
    content: str,
) -> OfficeDocumentComment:
    """Update a comment. Only the comment author can edit."""
    result = await db.execute(
        select(OfficeDocumentComment).where(OfficeDocumentComment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise NotFoundError("OfficeDocumentComment", str(comment_id))

    if comment.user_id != user.id:
        raise ForbiddenError("You can only edit your own comments.")

    comment.content = content
    comment.is_edited = True
    await db.commit()
    await db.refresh(comment)

    comment.user_name = user.full_name
    comment.user_email = user.email
    return comment


async def delete_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    user: User,
    is_admin: bool = False,
) -> None:
    """Delete a comment. Only the author or an admin can delete."""
    result = await db.execute(
        select(OfficeDocumentComment).where(OfficeDocumentComment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise NotFoundError("OfficeDocumentComment", str(comment_id))

    if comment.user_id != user.id and not is_admin:
        raise ForbiddenError("You can only delete your own comments.")

    doc_id = comment.document_id
    await db.delete(comment)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="office_document_comment_deleted",
        resource_type="office_document",
        resource_id=str(doc_id),
        details={"comment_id": str(comment_id)},
    )


# ---------------------------------------------------------------------------
# AI writing assistant
# ---------------------------------------------------------------------------

DOCS_AI_SYSTEM_PROMPT = """You are a writing assistant embedded in a document editor inside a business's \
all-in-one back-office suite. Help the user draft, rewrite, or answer questions about \
the current document.

When the user is asking you to rewrite or continue their selected text, return ONLY the \
replacement text -- no preamble, no markdown code fences, no commentary about what you did. \
When the user is asking a question, respond conversationally and concisely. Match the \
document's existing tone."""

# Keep the grounding context bounded -- content_text can be a full document.
_AI_ASSIST_CONTEXT_CHARS = 4000


def extract_plain_text(content_json: dict | None) -> str:
    """Best-effort plain-text extraction from a Tiptap/ProseMirror doc.

    Used to ground the AI assistant when OfficeDocument.content_text is
    empty -- today that field is only populated by save_yjs_state()'s Yjs
    decode, which most documents never touch until real-time collaboration
    (Task #67) is wired in, so relying on it alone would leave the
    assistant blind for nearly every document.
    """
    if not content_json:
        return ""

    lines: list[str] = []

    def inline_text(node: dict) -> str:
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(inline_text(child) for child in node.get("content", []))

    def walk_block(node: dict) -> None:
        node_type = node.get("type")
        if node_type in ("paragraph", "heading", "blockquote"):
            text = inline_text(node)
            if text.strip():
                lines.append(text)
        elif node_type in ("bulletList", "orderedList", "listItem"):
            for child in node.get("content", []):
                walk_block(child)
        else:
            for child in node.get("content", []):
                walk_block(child)

    for node in content_json.get("content", []):
        walk_block(node)

    return "\n".join(lines)


def stream_ai_assist(
    settings,
    doc_title: str,
    doc_content_text: str | None,
    instruction: str,
    selected_text: str | None,
):
    """Return an async generator yielding SSE chunks of a Claude response,
    grounded in the document's title/content and the user's selection.
    Mirrors app/ai/router.py:help_chat's streaming pattern.
    """
    import anthropic

    context_parts = [f'Document title: "{doc_title}"']
    if doc_content_text:
        context_parts.append(
            f"Document content (may be truncated):\n{doc_content_text[:_AI_ASSIST_CONTEXT_CHARS]}"
        )
    if selected_text:
        context_parts.append(f"Currently selected text:\n{selected_text}")
    context_parts.append(f"Instruction: {instruction}")
    user_message = "\n\n".join(context_parts)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate():
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=DOCS_AI_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return generate()
