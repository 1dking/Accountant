
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.collaboration.models import ActivityLog, ApprovalStatus, ApprovalWorkflow, Comment
from app.collaboration.schemas import ActivityFilter
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.core.websocket import websocket_manager
from app.notifications.service import create_notification


# ── Activity log helper ───────────────────────────────────────────────────────


async def log_activity(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> ActivityLog:
    """Create an activity log entry. Used by all services for audit trail."""
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_activity(
    db: AsyncSession,
    filters: ActivityFilter,
    pagination: PaginationParams,
) -> tuple[list[ActivityLog], int]:
    """Return paginated, filtered activity logs."""
    query = select(ActivityLog)
    count_query = select(func.count()).select_from(ActivityLog)

    conditions = []
    if filters.user_id is not None:
        conditions.append(ActivityLog.user_id == filters.user_id)
    if filters.action is not None:
        conditions.append(ActivityLog.action == filters.action)
    if filters.resource_type is not None:
        conditions.append(ActivityLog.resource_type == filters.resource_type)
    if filters.date_from is not None:
        conditions.append(ActivityLog.created_at >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(ActivityLog.created_at <= filters.date_to)

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total_count = await db.scalar(count_query) or 0

    result = await db.execute(
        query.order_by(ActivityLog.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    entries = list(result.scalars().all())
    return entries, total_count


# ── Comments ──────────────────────────────────────────────────────────────────


async def create_comment(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    parent_id: uuid.UUID | None = None,
) -> dict:
    """Create a comment on a document.

    Returns a dict with all comment fields plus user info.
    Side-effects: logs activity, sends notification to document owner, broadcasts WS event.
    """
    # Validate parent comment exists (if threaded reply)
    if parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(
                Comment.id == parent_id,
                Comment.document_id == document_id,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise NotFoundError("Comment", str(parent_id))

    comment = Comment(
        document_id=document_id,
        user_id=user_id,
        parent_id=parent_id,
        content=content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # Fetch the commenting user's info
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    # Log activity
    await log_activity(
        db,
        user_id=user_id,
        action="comment_created",
        resource_type="document",
        resource_id=str(document_id),
        details={"comment_id": str(comment.id)},
    )

    # Broadcast WebSocket event to all users
    await websocket_manager.broadcast(
        {
            "event": "comment_created",
            "data": {
                "comment_id": str(comment.id),
                "document_id": str(document_id),
                "user_id": str(user_id),
                "user_name": user.full_name,
                "content": content,
                "parent_id": str(parent_id) if parent_id else None,
            },
        },
    )

    return {
        "id": comment.id,
        "document_id": comment.document_id,
        "user_id": comment.user_id,
        "user_name": user.full_name,
        "user_email": user.email,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "is_edited": comment.is_edited,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


async def list_comments(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> list[dict]:
    """Return a flat list of all comments for a document, with user info.

    The frontend is responsible for building the reply tree from parent_id.
    """
    result = await db.execute(
        select(Comment, User.full_name, User.email)
        .join(User, Comment.user_id == User.id)
        .where(Comment.document_id == document_id)
        .order_by(Comment.created_at.asc())
    )
    rows = result.all()

    return [
        {
            "id": row[0].id,
            "document_id": row[0].document_id,
            "user_id": row[0].user_id,
            "user_name": row[1],
            "user_email": row[2],
            "parent_id": row[0].parent_id,
            "content": row[0].content,
            "is_edited": row[0].is_edited,
            "created_at": row[0].created_at,
            "updated_at": row[0].updated_at,
        }
        for row in rows
    ]


async def update_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> dict:
    """Update a comment. Only the comment author can edit."""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise NotFoundError("Comment", str(comment_id))

    if comment.user_id != user_id:
        raise ForbiddenError("You can only edit your own comments.")

    comment.content = content
    comment.is_edited = True
    await db.commit()
    await db.refresh(comment)

    # Fetch user info
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    return {
        "id": comment.id,
        "document_id": comment.document_id,
        "user_id": comment.user_id,
        "user_name": user.full_name,
        "user_email": user.email,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "is_edited": comment.is_edited,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


async def delete_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    is_admin: bool = False,
) -> None:
    """Delete a comment. Only the author or an admin can delete."""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise NotFoundError("Comment", str(comment_id))

    if comment.user_id != user_id and not is_admin:
        raise ForbiddenError("You can only delete your own comments.")

    await db.delete(comment)
    await db.commit()

    await log_activity(
        db,
        user_id=user_id,
        action="comment_deleted",
        resource_type="document",
        resource_id=str(comment.document_id),
        details={"comment_id": str(comment_id)},
    )


# ── Approvals ─────────────────────────────────────────────────────────────────


async def request_approval(
    db: AsyncSession,
    document_id: uuid.UUID,
    requested_by: uuid.UUID,
    assigned_to: uuid.UUID,
) -> ApprovalWorkflow:
    """Request approval for a document.

    Side-effects: notifies assigned user, logs activity, broadcasts WS event.
    """
    # Validate assigned user exists
    user_result = await db.execute(select(User).where(User.id == assigned_to))
    assigned_user = user_result.scalar_one_or_none()
    if assigned_user is None:
        raise NotFoundError("User", str(assigned_to))

    # Check for existing pending approval on the same document
    existing = await db.execute(
        select(ApprovalWorkflow).where(
            ApprovalWorkflow.document_id == document_id,
            ApprovalWorkflow.status == ApprovalStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValidationError(
            "There is already a pending approval for this document."
        )

    approval = ApprovalWorkflow(
        document_id=document_id,
        requested_by=requested_by,
        assigned_to=assigned_to,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    # Log activity
    await log_activity(
        db,
        user_id=requested_by,
        action="approval_requested",
        resource_type="document",
        resource_id=str(document_id),
        details={
            "approval_id": str(approval.id),
            "assigned_to": str(assigned_to),
        },
    )

    # Notify the assigned reviewer
    await create_notification(
        db,
        user_id=assigned_to,
        type="approval_request",
        title="Approval requested",
        message=f"You have been asked to review a document.",
        resource_type="document",
        resource_id=str(document_id),
    )

    # Broadcast WebSocket event
    await websocket_manager.broadcast(
        {
            "event": "approval_requested",
            "data": {
                "approval_id": str(approval.id),
                "document_id": str(document_id),
                "requested_by": str(requested_by),
                "assigned_to": str(assigned_to),
            },
        },
    )

    return approval


async def resolve_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    resolver_id: uuid.UUID,
    status: ApprovalStatus,
    comment: str | None = None,
    is_admin: bool = False,
) -> ApprovalWorkflow:
    """Resolve (approve/reject) an approval workflow.

    Only the assigned user or an admin can resolve.
    Side-effects: notifies requester, logs activity, broadcasts WS event.
    """
    if status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise ValidationError("Status must be 'approved' or 'rejected'.")

    result = await db.execute(
        select(ApprovalWorkflow).where(ApprovalWorkflow.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise NotFoundError("Approval", str(approval_id))

    if approval.status != ApprovalStatus.PENDING:
        raise ValidationError("This approval has already been resolved.")

    if approval.assigned_to != resolver_id and not is_admin:
        raise ForbiddenError("Only the assigned reviewer or an admin can resolve this approval.")

    approval.status = status
    approval.comment = comment
    approval.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(approval)

    # Log activity
    await log_activity(
        db,
        user_id=resolver_id,
        action=f"approval_{status.value}",
        resource_type="document",
        resource_id=str(approval.document_id),
        details={
            "approval_id": str(approval.id),
            "comment": comment,
        },
    )

    # Notify the requester
    await create_notification(
        db,
        user_id=approval.requested_by,
        type="approval_resolved",
        title=f"Document {status.value}",
        message=f"Your document approval request has been {status.value}.",
        resource_type="document",
        resource_id=str(approval.document_id),
    )

    # Broadcast WebSocket event
    await websocket_manager.broadcast(
        {
            "event": "approval_resolved",
            "data": {
                "approval_id": str(approval.id),
                "document_id": str(approval.document_id),
                "status": status.value,
                "resolved_by": str(resolver_id),
            },
        },
    )

    return approval


async def list_pending_approvals(
    db: AsyncSession,
    user_id: uuid.UUID,
    pagination: PaginationParams,
) -> tuple[list[ApprovalWorkflow], int]:
    """List pending approvals assigned to or requested by a user."""
    base_condition = ApprovalWorkflow.status == ApprovalStatus.PENDING

    # Show approvals assigned to the user OR requested by the user
    from sqlalchemy import or_

    user_condition = or_(
        ApprovalWorkflow.assigned_to == user_id,
        ApprovalWorkflow.requested_by == user_id,
    )

    total_count = await db.scalar(
        select(func.count())
        .select_from(ApprovalWorkflow)
        .where(base_condition, user_condition)
    ) or 0

    result = await db.execute(
        select(ApprovalWorkflow)
        .where(base_condition, user_condition)
        .order_by(ApprovalWorkflow.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    approvals = list(result.scalars().all())
    return approvals, total_count


async def cancel_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    user_id: uuid.UUID,
    is_admin: bool = False,
) -> ApprovalWorkflow:
    """Cancel a pending approval. Only the requester or an admin can cancel."""
    result = await db.execute(
        select(ApprovalWorkflow).where(ApprovalWorkflow.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise NotFoundError("Approval", str(approval_id))

    if approval.status != ApprovalStatus.PENDING:
        raise ValidationError("Only pending approvals can be cancelled.")

    if approval.requested_by != user_id and not is_admin:
        raise ForbiddenError("Only the requester or an admin can cancel this approval.")

    approval.status = ApprovalStatus.CANCELLED
    approval.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(approval)

    await log_activity(
        db,
        user_id=user_id,
        action="approval_cancelled",
        resource_type="document",
        resource_id=str(approval.document_id),
        details={"approval_id": str(approval.id)},
    )

    await websocket_manager.broadcast(
        {
            "event": "approval_cancelled",
            "data": {
                "approval_id": str(approval.id),
                "document_id": str(approval.document_id),
                "cancelled_by": str(user_id),
            },
        },
    )

    return approval
