
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.contacts import service
from app.contacts.models import ContactType
from app.contacts.schemas import (
    AcceptInvitationRequest,
    ActivityCreate,
    BulkTagRequest,
    ContactActivityResponse,
    ContactCreate,
    ContactFilter,
    ContactListItem,
    ContactResponse,
    ContactTagResponse,
    ContactUpdate,
    DuplicateGroup,
    FileShareCreate,
    FileShareResponse,
    InvitationCreate,
    InvitationResponse,
    MergeContactsRequest,
    TagRequest,
)
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# STATIC PATHS FIRST (must come before /{contact_id} to avoid conflicts)
# ---------------------------------------------------------------------------


@router.post("/bulk-tag")
async def bulk_tag(
    data: BulkTagRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    count = await service.bulk_tag(db, data.contact_ids, data.tag_name, current_user)
    return {"data": {"tagged_count": count}}


@router.get("/tags/all")
async def list_all_tags(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    tags = await service.list_all_tag_names(db, user=current_user)
    return {"data": tags}


@router.get("/duplicates/detect")
async def detect_duplicates(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    groups = await service.find_duplicates(db, user=current_user)
    return {"data": [DuplicateGroup(**g) for g in groups]}


@router.post("/merge")
async def merge_contacts(
    data: MergeContactsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    contact = await service.merge_contacts(
        db, data.primary_contact_id, data.duplicate_contact_ids, current_user
    )
    return {"data": ContactResponse.model_validate(contact)}


@router.post("/file-shares", status_code=201)
async def share_file(
    data: FileShareCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    share = await service.share_file(db, data, current_user)
    return {"data": FileShareResponse.model_validate(share)}


@router.delete("/file-shares/{share_id}")
async def remove_file_share(
    share_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    await service.remove_file_share(db, share_id, user=current_user)
    return {"data": {"message": "File share removed"}}


@router.post("/invitations", status_code=201)
async def create_invitation(
    data: InvitationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    invitation = await service.create_invitation(db, data, current_user)
    return {"data": InvitationResponse.model_validate(invitation)}


@router.get("/invitations")
async def list_invitations(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    invitations, total = await service.list_invitations(db, page, page_size)
    return {
        "data": [InvitationResponse.model_validate(i) for i in invitations],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/invitations/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    invitation = await service.resend_invitation(db, invitation_id)
    return {"data": InvitationResponse.model_validate(invitation)}


@router.post("/invitations/accept")
async def accept_invitation(
    data: AcceptInvitationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await service.accept_invitation(db, data.token, data.password, data.full_name)
    return {"data": {"message": "Account created", "user_id": str(user.id)}}


# ---------------------------------------------------------------------------
# Contacts CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_contacts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    type: ContactType | None = Query(None),
    is_active: bool | None = Query(None),
    tag: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
) -> dict:
    filters = ContactFilter(
        search=search, type=type, is_active=is_active,
        tag=tag, assigned_user_id=assigned_user_id,
    )
    contacts, meta = await service.list_contacts(db, filters, pagination, user=current_user)
    return {"data": [ContactListItem.model_validate(c) for c in contacts], "meta": meta}


@router.post("", status_code=201)
async def create_contact(
    data: ContactCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    contact = await service.create_contact(db, data, current_user)
    return {"data": ContactResponse.model_validate(contact)}


@router.get("/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    contact = await service.get_contact(db, contact_id, user=current_user)
    return {"data": ContactResponse.model_validate(contact)}


@router.put("/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    contact = await service.update_contact(db, contact_id, data, current_user)
    return {"data": ContactResponse.model_validate(contact)}


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_contact(db, contact_id, user=current_user)
    return {"data": {"message": "Contact deleted"}}


# ---------------------------------------------------------------------------
# Tags (under /{contact_id})
# ---------------------------------------------------------------------------


@router.post("/{contact_id}/tags", status_code=201)
async def add_tag(
    contact_id: uuid.UUID,
    data: TagRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    tag = await service.add_tag(db, contact_id, data.tag_name, current_user)
    return {"data": ContactTagResponse.model_validate(tag)}


@router.delete("/{contact_id}/tags/{tag_name}")
async def remove_tag(
    contact_id: uuid.UUID,
    tag_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    await service.remove_tag(db, contact_id, tag_name, user=current_user)
    return {"data": {"message": "Tag removed"}}


@router.get("/{contact_id}/tags")
async def list_tags(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    tags = await service.list_tags(db, contact_id, user=current_user)
    return {"data": [ContactTagResponse.model_validate(t) for t in tags]}


# ---------------------------------------------------------------------------
# Activities (under /{contact_id})
# ---------------------------------------------------------------------------


@router.get("/{contact_id}/activities")
async def list_activities(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    activities, total = await service.list_activities(db, contact_id, page, page_size, user=current_user)
    return {
        "data": [ContactActivityResponse.model_validate(a) for a in activities],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/{contact_id}/activities", status_code=201)
async def add_activity(
    contact_id: uuid.UUID,
    data: ActivityCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    activity = await service.log_contact_activity(
        db, contact_id, data.activity_type, data.title,
        data.description, data.reference_type, data.reference_id,
        current_user.id, user=current_user,
    )
    return {"data": ContactActivityResponse.model_validate(activity)}


# ---------------------------------------------------------------------------
# File Shares (under /{contact_id})
# ---------------------------------------------------------------------------


@router.get("/{contact_id}/file-shares")
async def list_file_shares(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    shares = await service.list_file_shares(db, contact_id, user=current_user)
    return {"data": [FileShareResponse.model_validate(s) for s in shares]}
