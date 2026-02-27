
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    GmailAccountResponse,
    GmailConnectResponse,
    GmailScanRequest,
    GmailScanResultResponse,
    GmailSendRequest,
)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------


@router.get("/connect", response_model=dict)
async def connect_gmail(
    request: Request,
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    auth_url = await service.get_google_auth_url(user.id, settings)
    return {"data": GmailConnectResponse(auth_url=auth_url)}


@router.get("/callback")
async def gmail_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    settings = _get_settings(request)
    await service.handle_oauth_callback(db, code, state, settings)
    return RedirectResponse(
        url="http://localhost:5173/settings?tab=gmail&connected=true"
    )


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


@router.get("/accounts", response_model=dict)
async def list_gmail_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accounts = await service.list_accounts(db, user.id)
    return {
        "data": [GmailAccountResponse.model_validate(a) for a in accounts],
    }


@router.delete("/accounts/{account_id}", response_model=dict)
async def disconnect_gmail_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.disconnect_account(db, account_id, user.id)
    return {"data": {"detail": "Gmail account disconnected"}}


# ---------------------------------------------------------------------------
# Email scanning
# ---------------------------------------------------------------------------


@router.post("/scan", response_model=dict)
async def scan_emails(
    data: GmailScanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    results = await service.scan_emails(
        db=db,
        gmail_account_id=data.gmail_account_id,
        query=data.query,
        max_results=data.max_results,
        user=user,
        settings=settings,
    )
    return {
        "data": [GmailScanResultResponse.model_validate(r) for r in results],
    }


@router.get("/results", response_model=dict)
async def list_scan_results(
    gmail_account_id: uuid.UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from .models import GmailScanResult, GmailAccount

    stmt = (
        select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailAccount.user_id == user.id)
    )
    if gmail_account_id:
        stmt = stmt.where(GmailScanResult.gmail_account_id == gmail_account_id)
    stmt = stmt.order_by(GmailScanResult.date.desc().nullslast())

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "data": [GmailScanResultResponse.model_validate(r) for r in rows],
    }


@router.post("/results/{result_id}/import", response_model=dict)
async def import_attachment(
    result_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    document_id = await service.import_attachment(db, result_id, user, settings)
    return {"data": {"document_id": str(document_id)}}


# ---------------------------------------------------------------------------
# Send email via Gmail
# ---------------------------------------------------------------------------


@router.post("/send", response_model=dict)
async def send_email_via_gmail(
    data: GmailSendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    await service.send_email_via_gmail(
        db=db,
        gmail_account_id=data.gmail_account_id,
        to=data.to,
        subject=data.subject,
        body_html=data.body_html,
        attachments=None,
        user=user,
        settings=settings,
    )
    return {"data": {"detail": f"Email sent via Gmail to {data.to}"}}
