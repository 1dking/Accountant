
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    GoogleCalendarAccountResponse,
    GoogleCalendarConnectResponse,
    GoogleCalendarInfo,
    SyncResult,
)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


class SetSyncCalendarRequest(BaseModel):
    google_calendar_id: str


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------


@router.get("/connect", response_model=dict)
async def connect_google_calendar(
    request: Request,
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    auth_url = await service.get_google_auth_url(user.id, settings)
    return {"data": GoogleCalendarConnectResponse(auth_url=auth_url)}


@router.get("/callback")
async def google_calendar_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    settings = _get_settings(request)
    await service.handle_oauth_callback(db, code, state, settings)
    base_url = settings.public_base_url.rstrip("/")
    return RedirectResponse(
        url=f"{base_url}/settings?tab=google-calendar&connected=true"
    )


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


@router.get("/accounts", response_model=dict)
async def list_google_calendar_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accounts = await service.list_accounts(db, user.id)
    return {
        "data": [GoogleCalendarAccountResponse.model_validate(a) for a in accounts],
    }


@router.delete("/accounts/{account_id}", response_model=dict)
async def disconnect_google_calendar_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.disconnect_account(db, account_id, user.id)
    return {"data": {"detail": "Google Calendar account disconnected"}}


# ---------------------------------------------------------------------------
# Calendar listing & sync configuration
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_id}/calendars", response_model=dict)
async def list_calendars(
    account_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = _get_settings(request)
    calendars = await service.list_google_calendars(db, account_id, user.id, settings)
    return {"data": [GoogleCalendarInfo(**c) for c in calendars]}


@router.post("/accounts/{account_id}/sync-calendar", response_model=dict)
async def set_sync_calendar(
    account_id: uuid.UUID,
    data: SetSyncCalendarRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    account = await service.set_sync_calendar(
        db, account_id, data.google_calendar_id, user.id
    )
    return {"data": GoogleCalendarAccountResponse.model_validate(account)}


# ---------------------------------------------------------------------------
# Manual sync trigger
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=dict)
async def trigger_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    accounts = await service.list_accounts(db, user.id)
    total_pulled = 0
    errors = []
    for account in accounts:
        try:
            count = await service.pull_events_from_google(db, account, settings)
            total_pulled += count
        except Exception as e:
            errors.append(str(e))
    return {"data": SyncResult(events_pulled=total_pulled, errors=errors)}
