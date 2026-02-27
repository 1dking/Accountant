
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.contacts import service
from app.contacts.models import ContactType
from app.contacts.schemas import (
    ContactCreate,
    ContactFilter,
    ContactListItem,
    ContactResponse,
    ContactUpdate,
)
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


@router.get("")
async def list_contacts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    type: ContactType | None = Query(None),
    is_active: bool | None = Query(None),
) -> dict:
    filters = ContactFilter(search=search, type=type, is_active=is_active)
    contacts, meta = await service.list_contacts(db, filters, pagination)
    return {"data": [ContactListItem.model_validate(c) for c in contacts], "meta": meta}


@router.post("", status_code=201)
async def create_contact(
    data: ContactCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    contact = await service.create_contact(db, data, current_user)
    return {"data": ContactResponse.model_validate(contact)}


@router.get("/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    contact = await service.get_contact(db, contact_id)
    return {"data": ContactResponse.model_validate(contact)}


@router.put("/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    contact = await service.update_contact(db, contact_id, data, current_user)
    return {"data": ContactResponse.model_validate(contact)}


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_contact(db, contact_id)
    return {"data": {"message": "Contact deleted"}}
