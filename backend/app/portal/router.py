"""FastAPI router for the client portal."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.portal import service
from app.portal.schemas import (
    PortalDashboard,
    PortalFile,
    PortalInvoice,
    PortalMeeting,
    PortalProposal,
)

router = APIRouter()


@router.get("/dashboard")
async def portal_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.CLIENT]))],
) -> dict:
    data = await service.get_portal_dashboard(db, current_user)
    return {"data": PortalDashboard(**data)}


@router.get("/invoices")
async def portal_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.CLIENT]))],
) -> dict:
    invoices = await service.get_portal_invoices(db, current_user)
    return {"data": [PortalInvoice(**i) for i in invoices]}


@router.get("/proposals")
async def portal_proposals(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.CLIENT]))],
) -> dict:
    proposals = await service.get_portal_proposals(db, current_user)
    return {"data": [PortalProposal(**p) for p in proposals]}


@router.get("/files")
async def portal_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.CLIENT]))],
) -> dict:
    files = await service.get_portal_files(db, current_user)
    return {"data": [PortalFile(**f) for f in files]}


@router.get("/meetings")
async def portal_meetings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.CLIENT]))],
) -> dict:
    meetings = await service.get_portal_meetings(db, current_user)
    return {"data": [PortalMeeting(**m) for m in meetings]}
