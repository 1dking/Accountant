
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact
from app.contacts.schemas import ContactCreate, ContactFilter, ContactUpdate
from app.core.exceptions import NotFoundError
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
    query = query.order_by(Contact.company_name).offset(pagination.offset).limit(pagination.page_size)
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
    return contact


async def delete_contact(db: AsyncSession, contact_id: uuid.UUID) -> None:
    contact = await get_contact(db, contact_id)
    await db.delete(contact)
    await db.commit()
