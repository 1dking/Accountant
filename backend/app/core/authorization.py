"""Centralized authorization helpers for ownership checks (IDOR prevention).

Every service function that reads/writes a resource must verify that the
requesting user is allowed to access it.  Admins bypass ownership checks;
all other roles must own the resource (matching the ownership column).
"""

import uuid

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.exceptions import ForbiddenError, NotFoundError


def is_admin(user: User) -> bool:
    """Return True if the user has the ADMIN role."""
    return user.role == Role.ADMIN


def authorize_owner(resource_owner_id: uuid.UUID, user: User, resource_name: str = "Resource") -> None:
    """Raise ForbiddenError if the user doesn't own the resource (admins bypass)."""
    if is_admin(user):
        return
    if resource_owner_id != user.id:
        # Return 404 instead of 403 to avoid leaking resource existence
        raise NotFoundError(resource_name, "requested")


def apply_ownership_filter(
    stmt: Select,
    column,
    user: User,
) -> Select:
    """Add a WHERE clause filtering by the ownership column unless admin.

    Usage:
        stmt = select(Document)
        stmt = apply_ownership_filter(stmt, Document.uploaded_by, user)
    """
    if is_admin(user):
        return stmt
    return stmt.where(column == user.id)


async def get_owned_resource(
    db: AsyncSession,
    stmt: Select,
    user: User,
    resource_name: str,
    resource_id: str,
):
    """Execute a query and verify the result is owned by the user.

    The ownership WHERE clause should already be in ``stmt`` via
    ``apply_ownership_filter``.  This helper just handles the
    not-found / forbidden logic.
    """
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundError(resource_name, resource_id)
    return obj
