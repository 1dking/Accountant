
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.collaboration.service import log_activity
from app.contacts.models import (
    ActivityType,
    ClientPortalAccount,
    Contact,
    ContactAccess,
    ContactActivity,
    ContactTag,
    FileShare,
    InvitationStatus,
    SharePermission,
    UserInvitation,
)
from app.contacts.schemas import (
    ContactCreate,
    ContactFilter,
    ContactUpdate,
    FileShareCreate,
    InvitationCreate,
)
from app.core.authorization import (
    apply_ownership_filter,
    apply_visibility_filter,
    authorize_owner,
    authorize_record,
    is_admin,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contacts CRUD
# ---------------------------------------------------------------------------


async def create_contact(
    db: AsyncSession, data: ContactCreate, user: User
) -> Contact:
    contact = Contact(
        **data.model_dump(),
        created_by=user.id,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    await log_activity(
        db,
        user_id=user.id,
        action="contact_created",
        resource_type="contact",
        resource_id=str(contact.id),
        details={
            "company_name": contact.company_name,
            "type": contact.type.value if contact.type else None,
        },
    )

    return contact


async def list_contacts(
    db: AsyncSession, filters: ContactFilter, pagination: PaginationParams, user: User | None = None
) -> tuple[list[Contact], dict]:
    query = select(Contact)

    if user is not None:
        # contact_col=Contact.id opts contacts into the share cascade: I see my
        # own, my reports' (if I'm a manager), and any contact shared with me.
        query = apply_visibility_filter(
            query, Contact.created_by, user, contact_col=Contact.id
        )

    if filters.search:
        term = f"%{filters.search}%"
        query = query.where(
            or_(
                Contact.company_name.ilike(term),
                Contact.contact_name.ilike(term),
                Contact.email.ilike(term),
            )
        )
    if filters.type is not None:
        query = query.where(Contact.type == filters.type)
    if filters.is_active is not None:
        query = query.where(Contact.is_active == filters.is_active)
    if filters.assigned_user_id is not None:
        query = query.where(Contact.assigned_user_id == filters.assigned_user_id)
    if filters.tag:
        tag_sub = select(ContactTag.contact_id).where(
            ContactTag.tag_name == filters.tag
        )
        query = query.where(Contact.id.in_(tag_sub))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(Contact.company_name)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(query)
    contacts = list(result.scalars().all())

    return contacts, build_pagination_meta(total, pagination)


async def get_contact(
    db: AsyncSession,
    contact_id: uuid.UUID,
    user: User | None = None,
    need_edit: bool = False,
) -> Contact:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if contact is None:
        raise NotFoundError("Contact", str(contact_id))
    if user is not None:
        await authorize_record(
            db,
            user,
            contact.created_by,
            contact_id=contact.id,
            need_edit=need_edit,
            resource_name="Contact",
        )
    return contact


async def update_contact(
    db: AsyncSession, contact_id: uuid.UUID, data: ContactUpdate, user: User
) -> Contact:
    # need_edit: a view-only share may read this contact but not change it.
    contact = await get_contact(db, contact_id, user=user, need_edit=True)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contact, key, value)
    await db.commit()
    await db.refresh(contact)

    await log_activity(
        db,
        user_id=user.id,
        action="contact_updated",
        resource_type="contact",
        resource_id=str(contact.id),
        details={"company_name": contact.company_name},
    )

    return contact


async def delete_contact(db: AsyncSession, contact_id: uuid.UUID, user: User | None = None) -> None:
    contact = await get_contact(db, contact_id)
    if user is not None:
        # Deliberately authorize_owner, not authorize_record: an edit-share lets a
        # colleague WORK the contact, not destroy it. Deleting someone's record out
        # from under them is the owner's call (or an admin's).
        authorize_owner(contact.created_by, user, "Contact")

    from app.invoicing.models import Invoice
    from app.estimates.models import Estimate

    invoice_count = (
        await db.execute(
            select(func.count()).where(Invoice.contact_id == contact_id)
        )
    ).scalar() or 0

    estimate_count = (
        await db.execute(
            select(func.count()).where(Estimate.contact_id == contact_id)
        )
    ).scalar() or 0

    if invoice_count or estimate_count:
        parts = []
        if invoice_count:
            parts.append(f"{invoice_count} invoice(s)")
        if estimate_count:
            parts.append(f"{estimate_count} estimate(s)")
        raise ConflictError(
            f"Cannot delete contact: it has {' and '.join(parts)}. "
            "Delete or reassign them first."
        )

    await db.delete(contact)
    await db.commit()


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


async def add_tag(
    db: AsyncSession, contact_id: uuid.UUID, tag_name: str, user: User
) -> ContactTag:
    await get_contact(db, contact_id, user=user)
    existing = await db.execute(
        select(ContactTag).where(
            ContactTag.contact_id == contact_id,
            ContactTag.tag_name == tag_name,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Tag '{tag_name}' already exists on this contact")

    tag = ContactTag(
        id=uuid.uuid4(),
        contact_id=contact_id,
        tag_name=tag_name,
        created_by=user.id,
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def remove_tag(
    db: AsyncSession, contact_id: uuid.UUID, tag_name: str, user: User | None = None
) -> None:
    if user is not None:
        await get_contact(db, contact_id, user=user)
    result = await db.execute(
        select(ContactTag).where(
            ContactTag.contact_id == contact_id,
            ContactTag.tag_name == tag_name,
        )
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        raise NotFoundError("ContactTag", f"{contact_id}:{tag_name}")
    await db.delete(tag)
    await db.commit()


async def bulk_tag(
    db: AsyncSession, contact_ids: list[uuid.UUID], tag_name: str, user: User
) -> int:
    # Check access to each contact before tagging
    for cid in contact_ids:
        await get_contact(db, cid, user=user)

    count = 0
    for cid in contact_ids:
        existing = await db.execute(
            select(ContactTag).where(
                ContactTag.contact_id == cid,
                ContactTag.tag_name == tag_name,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(ContactTag(
                id=uuid.uuid4(), contact_id=cid,
                tag_name=tag_name, created_by=user.id,
            ))
            count += 1
    await db.commit()
    return count


async def list_tags(db: AsyncSession, contact_id: uuid.UUID, user: User | None = None) -> list[ContactTag]:
    if user is not None:
        await get_contact(db, contact_id, user=user)
    result = await db.execute(
        select(ContactTag)
        .where(ContactTag.contact_id == contact_id)
        .order_by(ContactTag.tag_name)
    )
    return list(result.scalars().all())


async def list_all_tag_names(db: AsyncSession, user: User | None = None) -> list[str]:
    query = select(ContactTag.tag_name).distinct().order_by(ContactTag.tag_name)
    if user is not None:
        # Visible, not merely owned — a contact shared with me brings its tags,
        # otherwise the tag filter on my list would offer nothing for it.
        visible = apply_visibility_filter(
            select(Contact.id), Contact.created_by, user, contact_col=Contact.id
        )
        query = query.where(ContactTag.contact_id.in_(visible))
    result = await db.execute(query)
    return [r[0] for r in result.all()]


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


async def log_contact_activity(
    db: AsyncSession,
    contact_id: uuid.UUID,
    activity_type: ActivityType,
    title: str,
    description: str | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    user: User | None = None,
) -> ContactActivity:
    if user is not None:
        await get_contact(db, contact_id, user=user)
    activity = ContactActivity(
        id=uuid.uuid4(),
        contact_id=contact_id,
        activity_type=activity_type,
        title=title,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=user_id,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def list_activities(
    db: AsyncSession,
    contact_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    user: User | None = None,
) -> tuple[list[ContactActivity], int]:
    if user is not None:
        await get_contact(db, contact_id, user=user)
    count_q = select(func.count()).where(ContactActivity.contact_id == contact_id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(ContactActivity)
        .where(ContactActivity.contact_id == contact_id)
        .order_by(ContactActivity.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


async def find_duplicates(db: AsyncSession, user: User | None = None) -> list[dict]:
    groups = []

    # Base filter for ownership
    base_filter = select(Contact.id)
    if user is not None:
        base_filter = apply_ownership_filter(base_filter, Contact.created_by, user)

    # Email duplicates
    email_q = (
        select(Contact.email, func.count().label("cnt"))
        .where(Contact.email.isnot(None), Contact.email != "")
    )
    if user is not None:
        email_q = email_q.where(Contact.id.in_(base_filter))
    email_q = email_q.group_by(Contact.email).having(func.count() > 1)

    email_rows = (await db.execute(email_q)).all()
    for row in email_rows:
        ids_q = select(Contact.id).where(Contact.email == row[0])
        if user is not None:
            ids_q = apply_ownership_filter(ids_q, Contact.created_by, user)
        ids = [r[0] for r in (await db.execute(ids_q)).all()]
        groups.append({"field": "email", "value": row[0], "contact_ids": ids})

    # Phone duplicates
    phone_q = (
        select(Contact.phone, func.count().label("cnt"))
        .where(Contact.phone.isnot(None), Contact.phone != "")
    )
    if user is not None:
        phone_q = phone_q.where(Contact.id.in_(base_filter))
    phone_q = phone_q.group_by(Contact.phone).having(func.count() > 1)

    phone_rows = (await db.execute(phone_q)).all()
    for row in phone_rows:
        ids_q = select(Contact.id).where(Contact.phone == row[0])
        if user is not None:
            ids_q = apply_ownership_filter(ids_q, Contact.created_by, user)
        ids = [r[0] for r in (await db.execute(ids_q)).all()]
        groups.append({"field": "phone", "value": row[0], "contact_ids": ids})

    return groups


async def merge_contacts(
    db: AsyncSession,
    primary_id: uuid.UUID,
    duplicate_ids: list[uuid.UUID],
    user: User,
) -> Contact:
    primary = await get_contact(db, primary_id, user=user)

    from app.invoicing.models import Invoice
    from app.estimates.models import Estimate

    for dup_id in duplicate_ids:
        dup = await get_contact(db, dup_id, user=user)

        # Move invoices
        await db.execute(
            Invoice.__table__.update()
            .where(Invoice.contact_id == dup_id)
            .values(contact_id=primary_id)
        )
        # Move estimates
        await db.execute(
            Estimate.__table__.update()
            .where(Estimate.contact_id == dup_id)
            .values(contact_id=primary_id)
        )
        # Move tags
        dup_tags = await db.execute(
            select(ContactTag).where(ContactTag.contact_id == dup_id)
        )
        for tag in dup_tags.scalars().all():
            existing = await db.execute(
                select(ContactTag).where(
                    ContactTag.contact_id == primary_id,
                    ContactTag.tag_name == tag.tag_name,
                )
            )
            if not existing.scalar_one_or_none():
                tag.contact_id = primary_id
            else:
                await db.delete(tag)
        # Move activities
        await db.execute(
            ContactActivity.__table__.update()
            .where(ContactActivity.contact_id == dup_id)
            .values(contact_id=primary_id)
        )
        # Move file shares
        await db.execute(
            FileShare.__table__.update()
            .where(FileShare.contact_id == dup_id)
            .values(contact_id=primary_id)
        )

        await db.delete(dup)

    await db.commit()
    await db.refresh(primary)
    return primary


# ---------------------------------------------------------------------------
# File shares
# ---------------------------------------------------------------------------


async def share_file(
    db: AsyncSession, data: FileShareCreate, user: User
) -> FileShare:
    await get_contact(db, data.contact_id, user=user)
    share = FileShare(
        id=uuid.uuid4(),
        file_id=data.file_id,
        contact_id=data.contact_id,
        permission=data.permission,
        shared_by=user.id,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    await log_contact_activity(
        db, data.contact_id, ActivityType.FILE_SHARED,
        f"File shared", reference_type="document", reference_id=data.file_id,
        user_id=user.id,
    )

    return share


async def list_file_shares(
    db: AsyncSession, contact_id: uuid.UUID, user: User | None = None
) -> list[FileShare]:
    if user is not None:
        await get_contact(db, contact_id, user=user)
    result = await db.execute(
        select(FileShare)
        .where(FileShare.contact_id == contact_id)
        .order_by(FileShare.shared_at.desc())
    )
    return list(result.scalars().all())


async def list_contact_payments(
    db: AsyncSession, contact_id: uuid.UUID, user: User | None = None
) -> list[dict]:
    """Every payment received against this contact's invoices, newest first.

    Joined through Invoice because payments hang off the invoice, not the
    contact — there is no direct contact_id on InvoicePayment.
    """
    from app.invoicing.models import Invoice, InvoicePayment

    if user is not None:
        await get_contact(db, contact_id, user=user)

    result = await db.execute(
        select(InvoicePayment, Invoice)
        .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
        .where(Invoice.contact_id == contact_id)
        .order_by(InvoicePayment.date.desc(), InvoicePayment.created_at.desc())
    )

    return [
        {
            "id": payment.id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "invoice_total": float(invoice.total),
            "amount": float(payment.amount),
            "currency": invoice.currency,
            "date": str(payment.date),
            "payment_method": payment.payment_method,
            "reference": payment.reference,
            "notes": payment.notes,
        }
        for payment, invoice in result.all()
    ]


async def list_shared_files_for_portal(
    db: AsyncSession, contact_id: uuid.UUID
) -> list[dict]:
    from app.documents.models import Document

    q = (
        select(FileShare, Document)
        .join(Document, Document.id == FileShare.file_id)
        .where(FileShare.contact_id == contact_id)
        .order_by(FileShare.shared_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "share_id": share.id,
            "file_id": doc.id,
            "filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "file_size": doc.file_size,
            "permission": share.permission.value,
            "shared_at": share.shared_at,
        }
        for share, doc in rows
    ]


async def remove_file_share(db: AsyncSession, share_id: uuid.UUID, user: User | None = None) -> None:
    result = await db.execute(select(FileShare).where(FileShare.id == share_id))
    share = result.scalar_one_or_none()
    if share is None:
        raise NotFoundError("FileShare", str(share_id))
    if user is not None:
        await get_contact(db, share.contact_id, user=user)
    await db.delete(share)
    await db.commit()


# ---------------------------------------------------------------------------
# Client Portal Accounts
# ---------------------------------------------------------------------------


async def get_portal_account_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> ClientPortalAccount | None:
    result = await db.execute(
        select(ClientPortalAccount).where(ClientPortalAccount.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_portal_contact(
    db: AsyncSession, user_id: uuid.UUID
) -> Contact | None:
    portal = await get_portal_account_by_user(db, user_id)
    if portal is None:
        return None
    return await get_contact(db, portal.contact_id)


# ---------------------------------------------------------------------------
# User Invitations
# ---------------------------------------------------------------------------


async def create_invitation(
    db: AsyncSession, data: InvitationCreate, user: User
) -> UserInvitation:
    existing = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"User with email {data.email} already exists")

    token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid.uuid4(),
        email=data.email,
        role=data.role,
        token=token,
        invited_by=user.id,
        contact_id=data.contact_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_invitation(
    db: AsyncSession,
    token: str,
    password: str,
    full_name: str,
) -> User:
    result = await db.execute(
        select(UserInvitation).where(
            UserInvitation.token == token,
            UserInvitation.status == InvitationStatus.PENDING,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise NotFoundError("Invitation", token)

    now = datetime.now(timezone.utc)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        invitation.status = InvitationStatus.EXPIRED
        await db.commit()
        raise ConflictError("Invitation has expired")

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=invitation.email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=Role(invitation.role),
        is_active=True,
    )
    db.add(user)

    # If contact_id provided, create portal account
    if invitation.contact_id and invitation.role == Role.CLIENT.value:
        portal = ClientPortalAccount(
            id=uuid.uuid4(),
            contact_id=invitation.contact_id,
            user_id=user.id,
        )
        db.add(portal)

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = now
    await db.commit()
    await db.refresh(user)
    return user


async def list_invitations(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> tuple[list[UserInvitation], int]:
    count_q = select(func.count(UserInvitation.id))
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(UserInvitation)
        .order_by(UserInvitation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def resend_invitation(
    db: AsyncSession, invitation_id: uuid.UUID
) -> UserInvitation:
    result = await db.execute(
        select(UserInvitation).where(UserInvitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise NotFoundError("Invitation", str(invitation_id))

    invitation.token = secrets.token_urlsafe(48)
    invitation.status = InvitationStatus.PENDING
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.commit()
    await db.refresh(invitation)
    return invitation


# ---------------------------------------------------------------------------
# Explicit sharing — the escape hatch from owner-private
# ---------------------------------------------------------------------------


async def share_contact(
    db: AsyncSession,
    contact_id: uuid.UUID,
    user: User,
    target_user_id: uuid.UUID,
    permission: SharePermission = SharePermission.VIEW,
) -> ContactAccess:
    """Grant a colleague access to one contact. Upsert — re-sharing changes the
    permission rather than piling up rows.

    Only the contact's OWNER (or an admin) may share. Deliberately authorize_owner
    and not authorize_record: you cannot re-share something that was merely shared
    with you, or one grant would leak transitively across the whole team.
    """
    contact = await get_contact(db, contact_id)
    authorize_owner(contact.created_by, user, "Contact")

    target = (
        await db.execute(select(User).where(User.id == target_user_id))
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError("User", str(target_user_id))
    if target.role == Role.CLIENT:
        # A client's only surface is the portal, scoped by ClientPortalAccount.
        # Handing them a CRM grant would walk them straight into the book.
        raise ForbiddenError("Contacts cannot be shared with a client portal user.")
    if target.id == contact.created_by:
        raise ConflictError("That user already owns this contact.")

    existing = (
        await db.execute(
            select(ContactAccess).where(
                ContactAccess.contact_id == contact_id,
                ContactAccess.user_id == target_user_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.permission = permission
        existing.granted_by = user.id
        access = existing
    else:
        access = ContactAccess(
            id=uuid.uuid4(),
            contact_id=contact_id,
            user_id=target_user_id,
            permission=permission,
            granted_by=user.id,
        )
        db.add(access)

    await db.commit()
    await db.refresh(access)

    await log_activity(
        db,
        user_id=user.id,
        action="contact_shared",
        resource_type="contact",
        resource_id=str(contact_id),
        details={"target_user_id": str(target_user_id), "permission": permission.value},
    )

    try:
        from app.notifications.service import create_notification

        await create_notification(
            db,
            user_id=target_user_id,
            type="contact_shared",
            title=f"{user.full_name} shared a contact with you",
            message=f"{contact.company_name} — {permission.value} access",
            resource_type="contact",
            resource_id=str(contact_id),
            link_path=f"/contacts/{contact_id}",
            contact_id=contact_id,
        )
    except Exception:  # noqa: BLE001 — a failed notification must not undo the share
        logger.exception("contact_share.notification_failed contact_id=%s", contact_id)

    return access


async def unshare_contact(
    db: AsyncSession, contact_id: uuid.UUID, user: User, target_user_id: uuid.UUID
) -> None:
    """Revoke a colleague's access. Owner or admin only."""
    contact = await get_contact(db, contact_id)
    authorize_owner(contact.created_by, user, "Contact")

    access = (
        await db.execute(
            select(ContactAccess).where(
                ContactAccess.contact_id == contact_id,
                ContactAccess.user_id == target_user_id,
            )
        )
    ).scalar_one_or_none()
    if access is None:
        raise NotFoundError("ContactAccess", str(target_user_id))

    await db.delete(access)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="contact_unshared",
        resource_type="contact",
        resource_id=str(contact_id),
        details={"target_user_id": str(target_user_id)},
    )


async def list_contact_collaborators(
    db: AsyncSession, contact_id: uuid.UUID, user: User
) -> list[dict]:
    """Who this contact is shared with.

    Anyone who can see the contact can see who else it is shared with — if you are
    working a file, you should know who else is working it.
    """
    await get_contact(db, contact_id, user=user)

    rows = (
        await db.execute(
            select(ContactAccess, User)
            .join(User, User.id == ContactAccess.user_id)
            .where(ContactAccess.contact_id == contact_id)
            .order_by(ContactAccess.created_at.desc())
        )
    ).all()

    return [
        {
            "id": access.id,
            "user_id": access.user_id,
            "user_name": target.full_name,
            "user_email": target.email,
            "permission": access.permission.value,
            "granted_by": access.granted_by,
            "created_at": access.created_at,
        }
        for access, target in rows
    ]


# ---------------------------------------------------------------------------
# Ownership transfer — the offboarding path
# ---------------------------------------------------------------------------


async def transfer_contact_ownership(
    db: AsyncSession, contact_id: uuid.UUID, user: User, new_owner_id: uuid.UUID
) -> Contact:
    """Hand a contact — and its whole file — to another employee. Admin only.

    ``created_by`` is immutable, so without this, a departing employee's book would
    be reachable only by an admin, forever. Reassigning the contact moves the file
    with it: invoices, proposals, tasks and calls resolve visibility through their
    contact, so they follow automatically.
    """
    if not is_admin(user):
        raise ForbiddenError("Only an admin can transfer ownership of a contact.")

    contact = await get_contact(db, contact_id)

    new_owner = (
        await db.execute(select(User).where(User.id == new_owner_id))
    ).scalar_one_or_none()
    if new_owner is None:
        raise NotFoundError("User", str(new_owner_id))
    if new_owner.role == Role.CLIENT:
        raise ForbiddenError("A client portal user cannot own a contact.")

    previous_owner_id = contact.created_by
    contact.created_by = new_owner_id

    # Any share TO the new owner is now redundant — they own it outright.
    await db.execute(
        sa_delete(ContactAccess).where(
            ContactAccess.contact_id == contact_id,
            ContactAccess.user_id == new_owner_id,
        )
    )

    await db.commit()
    await db.refresh(contact)

    await log_activity(
        db,
        user_id=user.id,
        action="contact_ownership_transferred",
        resource_type="contact",
        resource_id=str(contact_id),
        details={
            "previous_owner_id": str(previous_owner_id),
            "new_owner_id": str(new_owner_id),
        },
    )
    return contact


async def transfer_all_contacts(
    db: AsyncSession, user: User, from_user_id: uuid.UUID, to_user_id: uuid.UUID
) -> int:
    """Reassign an entire book from one employee to another. Admin only.

    The bulk offboarding path: a VA or salesperson leaves and their whole desk goes
    to whoever picks it up. Returns the number of contacts moved.
    """
    if not is_admin(user):
        raise ForbiddenError("Only an admin can transfer a book of contacts.")

    to_user = (
        await db.execute(select(User).where(User.id == to_user_id))
    ).scalar_one_or_none()
    if to_user is None:
        raise NotFoundError("User", str(to_user_id))
    if to_user.role == Role.CLIENT:
        raise ForbiddenError("A client portal user cannot own contacts.")

    contact_ids = [
        r[0]
        for r in (
            await db.execute(
                select(Contact.id).where(Contact.created_by == from_user_id)
            )
        ).all()
    ]
    if not contact_ids:
        return 0

    await db.execute(
        sa_update(Contact)
        .where(Contact.created_by == from_user_id)
        .values(created_by=to_user_id)
    )
    await db.execute(
        sa_delete(ContactAccess).where(
            ContactAccess.contact_id.in_(contact_ids),
            ContactAccess.user_id == to_user_id,
        )
    )
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="contact_book_transferred",
        resource_type="user",
        resource_id=str(from_user_id),
        details={"to_user_id": str(to_user_id), "contacts_moved": len(contact_ids)},
    )
    return len(contact_ids)
