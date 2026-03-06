
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.collaboration.service import log_activity
from app.contacts.models import (
    ActivityType,
    ClientPortalAccount,
    Contact,
    ContactActivity,
    ContactTag,
    FileShare,
    InvitationStatus,
    UserInvitation,
)
from app.contacts.schemas import (
    ContactCreate,
    ContactFilter,
    ContactUpdate,
    FileShareCreate,
    InvitationCreate,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta


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
    db: AsyncSession, filters: ContactFilter, pagination: PaginationParams
) -> tuple[list[Contact], dict]:
    query = select(Contact)

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


async def get_contact(db: AsyncSession, contact_id: uuid.UUID) -> Contact:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if contact is None:
        raise NotFoundError("Contact", str(contact_id))
    return contact


async def update_contact(
    db: AsyncSession, contact_id: uuid.UUID, data: ContactUpdate, user: User
) -> Contact:
    contact = await get_contact(db, contact_id)
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


async def delete_contact(db: AsyncSession, contact_id: uuid.UUID) -> None:
    contact = await get_contact(db, contact_id)

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
    await get_contact(db, contact_id)
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
    db: AsyncSession, contact_id: uuid.UUID, tag_name: str
) -> None:
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


async def list_tags(db: AsyncSession, contact_id: uuid.UUID) -> list[ContactTag]:
    result = await db.execute(
        select(ContactTag)
        .where(ContactTag.contact_id == contact_id)
        .order_by(ContactTag.tag_name)
    )
    return list(result.scalars().all())


async def list_all_tag_names(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(ContactTag.tag_name).distinct().order_by(ContactTag.tag_name)
    )
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
) -> ContactActivity:
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
) -> tuple[list[ContactActivity], int]:
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


async def find_duplicates(db: AsyncSession) -> list[dict]:
    groups = []

    # Email duplicates
    email_q = (
        select(Contact.email, func.count().label("cnt"))
        .where(Contact.email.isnot(None), Contact.email != "")
        .group_by(Contact.email)
        .having(func.count() > 1)
    )
    email_rows = (await db.execute(email_q)).all()
    for row in email_rows:
        ids_q = select(Contact.id).where(Contact.email == row[0])
        ids = [r[0] for r in (await db.execute(ids_q)).all()]
        groups.append({"field": "email", "value": row[0], "contact_ids": ids})

    # Phone duplicates
    phone_q = (
        select(Contact.phone, func.count().label("cnt"))
        .where(Contact.phone.isnot(None), Contact.phone != "")
        .group_by(Contact.phone)
        .having(func.count() > 1)
    )
    phone_rows = (await db.execute(phone_q)).all()
    for row in phone_rows:
        ids_q = select(Contact.id).where(Contact.phone == row[0])
        ids = [r[0] for r in (await db.execute(ids_q)).all()]
        groups.append({"field": "phone", "value": row[0], "contact_ids": ids})

    return groups


async def merge_contacts(
    db: AsyncSession,
    primary_id: uuid.UUID,
    duplicate_ids: list[uuid.UUID],
    user: User,
) -> Contact:
    primary = await get_contact(db, primary_id)

    from app.invoicing.models import Invoice
    from app.estimates.models import Estimate

    for dup_id in duplicate_ids:
        dup = await get_contact(db, dup_id)

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
    db: AsyncSession, contact_id: uuid.UUID
) -> list[FileShare]:
    result = await db.execute(
        select(FileShare)
        .where(FileShare.contact_id == contact_id)
        .order_by(FileShare.shared_at.desc())
    )
    return list(result.scalars().all())


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


async def remove_file_share(db: AsyncSession, share_id: uuid.UUID) -> None:
    result = await db.execute(select(FileShare).where(FileShare.id == share_id))
    share = result.scalar_one_or_none()
    if share is None:
        raise NotFoundError("FileShare", str(share_id))
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
