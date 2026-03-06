
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.forms import service
from app.forms.schemas import (
    FormCreate,
    FormListItem,
    FormResponse,
    FormSubmissionResponse,
    FormSubmitRequest,
    FormUpdate,
    PublicFormResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# PUBLIC ENDPOINTS (static paths - must come before /{form_id})
# ---------------------------------------------------------------------------


@router.get("/public/{form_id}")
async def get_public_form(
    form_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public endpoint for rendering a form (no auth required)."""
    form = await service.get_public_form(db, form_id)
    return {"data": PublicFormResponse.model_validate(form)}


@router.post("/public/{form_id}/submit", status_code=201)
async def submit_public_form(
    form_id: uuid.UUID,
    data: FormSubmitRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public endpoint for submitting a form (no auth required)."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]
    submission = await service.submit_form(
        db, form_id, data.data, ip_address, user_agent
    )
    return {"data": FormSubmissionResponse.model_validate(submission)}


# ---------------------------------------------------------------------------
# AUTHENTICATED ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("")
async def list_forms(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    items, total = await service.list_forms(db, page, page_size)
    return {
        "data": [FormListItem(**item) for item in items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("", status_code=201)
async def create_form(
    data: FormCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    form = await service.create_form(db, data, current_user)
    return {"data": FormResponse.model_validate(form)}


@router.get("/{form_id}")
async def get_form(
    form_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    form = await service.get_form(db, form_id)
    return {"data": FormResponse.model_validate(form)}


@router.put("/{form_id}")
async def update_form(
    form_id: uuid.UUID,
    data: FormUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    form = await service.update_form(db, form_id, data)
    return {"data": FormResponse.model_validate(form)}


@router.delete("/{form_id}")
async def delete_form(
    form_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_form(db, form_id)
    return {"data": {"message": "Form deleted"}}


@router.get("/{form_id}/submissions")
async def list_submissions(
    form_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    submissions, total = await service.list_submissions(db, form_id, page, page_size)
    return {
        "data": [FormSubmissionResponse.model_validate(s) for s in submissions],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }
