
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.collaboration.service import log_activity
from app.contacts.models import Contact
from app.contacts.schemas import ContactCreate, ContactFilter, ContactUpdate
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta


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

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch
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

    # Prevent cascade-deleting invoices/estimates that reference this contact
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
