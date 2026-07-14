"""Centralized authorization helpers for ownership checks (IDOR prevention).

Records are PRIVATE TO THEIR OWNER. Every employee has their own section: two
people working the phones must not see each other's contacts. Only an ADMIN (the
agency owner) sees across everyone. Where a colleague genuinely needs a record,
it is shared with them EXPLICITLY — sharing is an action, never a default.

This was briefly changed to a shared-workspace model on the strength of a test
suite that asserted a viewer could read another user's contact. Those tests
encoded the wrong product: they were rewritten, not obeyed. If you are tempted to
loosen these checks again because "the viewer role can't see anything" — that is
the intended behaviour, not a bug. A viewer sees what has been shared with it.
"""

import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.exceptions import ForbiddenError, NotFoundError


def is_admin(user: User) -> bool:
    """Return True if the user has the ADMIN role."""
    return user.role == Role.ADMIN


def authorize_owner(resource_owner_id: uuid.UUID, user: User, resource_name: str = "Resource") -> None:
    """Only the creator — or an admin — may touch this record.

    The strict form, with no manager reach and no share escape hatch. Use it for
    resources that are nobody else's business no matter what: SMTP configs (they
    hold decryptable mail passwords), a user's own Drive documents, meetings.
    For business records that can be shared, use authorize_record().
    """
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
    """List-query counterpart of authorize_owner.

    Usage:
        stmt = select(Document)
        stmt = apply_ownership_filter(stmt, Document.uploaded_by, user)
    """
    if is_admin(user):
        return stmt
    return stmt.where(column == user.id)


# ---------------------------------------------------------------------------
# Visibility: ownership + manager reach + explicit shares
# ---------------------------------------------------------------------------
#
# Three ways to reach a business record, in order of cheapness:
#   1. you own it
#   2. you are a MANAGER and its owner reports to you
#   3. it is a contact shared with you — or it HANGS OFF a contact shared with
#      you (the cascade: a contact you can't see the file of is just a name)
#
# ADMIN short-circuits all of it.


def _visible_owner_ids(user: User) -> Select | None:
    """Subquery: whose records may this user see, by ownership alone?

    Returns None for an admin, meaning "no restriction" — the caller adds no
    WHERE clause at all rather than building a list of every user id.
    """
    if is_admin(user):
        return None
    if user.role == Role.MANAGER:
        # Own records + direct reports'. One level deep: a manager of managers
        # does not inherit the whole subtree. Deliberate — see Role docstring.
        return select(User.id).where(
            or_(User.id == user.id, User.manager_id == user.id)
        )
    return select(User.id).where(User.id == user.id)


def _can_be_granted_shares(user: User) -> bool:
    """A CLIENT must never gain reach through a ContactAccess row.

    Their only legitimate surface is the portal, scoped by ClientPortalAccount. A
    stray grant — however it got written — must not become a way for a portal user
    to walk into the CRM.
    """
    return user.role != Role.CLIENT


def apply_visibility_filter(
    stmt: Select,
    owner_col,
    user: User,
    *,
    contact_col=None,
    require_edit: bool = False,
) -> Select:
    """List-query workhorse for shareable business records.

    ``contact_col`` opts the model into the share cascade: pass ``Contact.id`` for
    contacts themselves, or ``Invoice.contact_id`` / ``Task.contact_id`` etc. for
    records hanging off a contact. Omit it for models with no contact (budgets,
    recurring rules) and it degrades to plain ownership.

    A record with ``contact_id IS NULL`` (a standalone task, an untethered call)
    gets no cascade and stays private to its owner. Correct: it was never part of
    anyone's file.
    """
    from app.contacts.models import ContactAccess, SharePermission

    if is_admin(user):
        return stmt

    cond = owner_col.in_(_visible_owner_ids(user))

    if contact_col is not None and _can_be_granted_shares(user):
        shared = select(ContactAccess.contact_id).where(
            ContactAccess.user_id == user.id
        )
        if require_edit:
            shared = shared.where(ContactAccess.permission == SharePermission.EDIT)
        cond = or_(cond, contact_col.in_(shared))

    return stmt.where(cond)


async def get_contact_permission(db: AsyncSession, contact_id: uuid.UUID, user: User):
    """The SharePermission this user has been granted on a contact, or None."""
    from app.contacts.models import ContactAccess

    if not _can_be_granted_shares(user):
        return None
    row = await db.execute(
        select(ContactAccess.permission).where(
            ContactAccess.contact_id == contact_id,
            ContactAccess.user_id == user.id,
        )
    )
    return row.scalar_one_or_none()


async def _is_direct_report(db: AsyncSession, owner_id: uuid.UUID, manager_id: uuid.UUID) -> bool:
    row = await db.execute(
        select(User.id).where(User.id == owner_id, User.manager_id == manager_id)
    )
    return row.scalar_one_or_none() is not None


async def authorize_record(
    db: AsyncSession,
    user: User,
    owner_id: uuid.UUID,
    *,
    contact_id: uuid.UUID | None = None,
    need_edit: bool = False,
    resource_name: str = "Resource",
) -> None:
    """Single-record counterpart of apply_visibility_filter.

    Raises NotFoundError (404) when the record is invisible — never 403, because a
    403 confirms it exists and lets someone map a colleague's book by probing ids.

    Raises ForbiddenError (403) only in the one case where the record IS visible
    but the action isn't allowed: you hold a view-only share and tried to write.
    Here 403 leaks nothing you weren't already shown.
    """
    from app.contacts.models import SharePermission

    if is_admin(user) or owner_id == user.id:
        return

    if user.role == Role.MANAGER and await _is_direct_report(db, owner_id, user.id):
        return

    if contact_id is not None:
        permission = await get_contact_permission(db, contact_id, user)
        if permission == SharePermission.EDIT:
            return
        if permission == SharePermission.VIEW:
            if not need_edit:
                return
            raise ForbiddenError(
                f"This {resource_name.lower()} was shared with you as view-only."
            )

    raise NotFoundError(resource_name, "requested")


def apply_cashbook_filter(
    stmt: Select,
    user_id_col,
    org_id_col,
    user: User,
) -> Select:
    """Filter cashbook resources by org_id (if user has org access) or user_id.

    - Admin with org access: filter by org_id (sees all org data)
    - Admin without org access: no filter (sees everything — legacy behavior)
    - Non-admin with org access + org_id: filter by org_id (shared org cashbook)
    - Non-admin without org access: filter by user_id (personal cashbook)
    """
    if user.cashbook_access == "org" and user.org_id is not None:
        return stmt.where(org_id_col == user.org_id)
    if is_admin(user):
        return stmt
    return stmt.where(user_id_col == user.id)


def authorize_cashbook_owner(
    resource_user_id: uuid.UUID,
    resource_org_id: uuid.UUID | None,
    user: User,
    resource_name: str = "Resource",
) -> None:
    """Check if user can access a cashbook resource (owns it or shares org)."""
    if is_admin(user):
        return
    # Org access: allow if the resource belongs to the same org
    if (
        user.cashbook_access == "org"
        and user.org_id is not None
        and resource_org_id == user.org_id
    ):
        return
    # Personal access: must own it
    if resource_user_id == user.id:
        return
    raise NotFoundError(resource_name, "requested")


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
