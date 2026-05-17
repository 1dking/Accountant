
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


# ---------------------------------------------------------------------------
# Unified Conversations Thread (SMS + voicemails)
# ---------------------------------------------------------------------------


@router.get("/{contact_id}/conversations")
async def list_contact_conversations(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return SMS messages + voicemail entries for a contact, sorted
    chronologically (oldest first — frontend renders newest-at-bottom
    for typical SMS-thread feel)."""
    from sqlalchemy import select
    from app.communication.models import CallLog, SmsMessage

    sms_rows = await db.execute(
        select(SmsMessage)
        .where(SmsMessage.contact_id == contact_id)
        .order_by(SmsMessage.created_at.desc())
        .limit(100)
    )
    voicemail_rows = await db.execute(
        select(CallLog)
        .where(
            CallLog.contact_id == contact_id,
            CallLog.kind == "voicemail",
        )
        .order_by(CallLog.created_at.desc())
        .limit(50)
    )

    events: list[dict] = []
    for sms in sms_rows.scalars().all():
        events.append({
            "id": str(sms.id),
            "type": "sms_in" if sms.direction == "inbound" else "sms_out",
            "timestamp": sms.created_at.isoformat() if sms.created_at else None,
            "body": sms.body,
            "direction": sms.direction,
            "status": sms.status,
            "from_number": sms.from_number,
            "to_number": sms.to_number,
            "ref_id": str(sms.id),
        })
    for vm in voicemail_rows.scalars().all():
        events.append({
            "id": f"vm:{vm.id}",
            "type": "voicemail",
            "timestamp": vm.created_at.isoformat() if vm.created_at else None,
            "body": vm.voicemail_transcript or "",
            "direction": "inbound",
            "status": vm.voicemail_transcript_status,
            "from_number": vm.from_number,
            "to_number": vm.to_number,
            "recording_url_path": (
                f"/api/communication/calls/{vm.id}/recording" if vm.recording_sid else None
            ),
            "recording_duration_seconds": vm.recording_duration_seconds,
            "ref_id": str(vm.id),
        })

    # Sort by timestamp ascending (oldest first) so the frontend can render
    # in the natural SMS direction. None-timestamps sort to start.
    events.sort(key=lambda e: e["timestamp"] or "")
    return {"data": events}


# ---------------------------------------------------------------------------
# Contact Memories (AI-extracted)
# ---------------------------------------------------------------------------


@router.get("/{contact_id}/memories")
async def list_contact_memories(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    from sqlalchemy import select
    from app.contacts.models import ContactMemory

    result = await db.execute(
        select(ContactMemory)
        .where(ContactMemory.contact_id == contact_id)
        .order_by(ContactMemory.created_at.desc())
        .limit(100)
    )
    memories = list(result.scalars().all())
    return {
        "data": [
            {
                "id": str(m.id),
                "contact_id": str(m.contact_id),
                "source_type": m.source_type,
                "source_id": str(m.source_id) if m.source_id else None,
                "summary": m.summary,
                "commitments": m.commitments,
                "cares_about": m.cares_about,
                "talking_points": m.talking_points,
                "raw_input": m.raw_input,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]
    }


@router.post("/{contact_id}/memories", status_code=201)
async def create_contact_memory(
    contact_id: uuid.UUID,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Create a manual memory entry. Runs AI extraction on raw_input."""
    from fastapi import HTTPException
    from app.communication.memory_extraction import extract_memory
    from app.contacts.models import Contact, ContactMemory

    raw_input = (body.get("raw_input") or "").strip()
    if not raw_input:
        raise HTTPException(status_code=400, detail="raw_input is required")
    if len(raw_input) > 10000:
        raise HTTPException(status_code=400, detail="raw_input exceeds 10000 chars")

    # Confirm contact exists
    from sqlalchemy import select
    contact_row = await db.execute(select(Contact).where(Contact.id == contact_id))
    if contact_row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    try:
        extracted = await extract_memory(
            raw_text=raw_input,
            source_type=body.get("source_type", "manual"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Memory extraction failed: {str(e)[:120]}"
        )

    memory = ContactMemory(
        id=uuid.uuid4(),
        contact_id=contact_id,
        user_id=current_user.id,
        source_type=body.get("source_type", "manual"),
        source_id=None,
        summary=extracted["summary"],
        commitments=extracted["commitments"],
        cares_about=extracted["cares_about"],
        talking_points=extracted["talking_points"],
        raw_input=raw_input,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return {
        "data": {
            "id": str(memory.id),
            "contact_id": str(memory.contact_id),
            "source_type": memory.source_type,
            "summary": memory.summary,
            "commitments": memory.commitments,
            "cares_about": memory.cares_about,
            "talking_points": memory.talking_points,
            "raw_input": memory.raw_input,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
        }
    }


@router.delete("/{contact_id}/memories/{memory_id}")
async def delete_contact_memory(
    contact_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.contacts.models import ContactMemory

    result = await db.execute(
        select(ContactMemory).where(
            ContactMemory.id == memory_id,
            ContactMemory.contact_id == contact_id,
        )
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.delete(memory)
    await db.commit()
    return {"data": {"deleted": True}}
