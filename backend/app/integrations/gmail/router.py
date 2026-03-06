
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    BulkDeleteRequest,
    EmailImportRequest,
    EmailImportResponse,
    EmailParseResponse,
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
    base_url = _get_settings(request).public_base_url.rstrip("/")
    return RedirectResponse(
        url=f"{base_url}/settings?tab=gmail&connected=true"
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
    results, next_page_token = await service.scan_emails(
        db=db,
        gmail_account_id=data.gmail_account_id,
        query=data.query,
        max_results=data.max_results,
        user=user,
        settings=settings,
        after_date=data.after_date,
        before_date=data.before_date,
        page_token=data.page_token,
    )
    return {
        "data": [GmailScanResultResponse.model_validate(r) for r in results],
        "meta": {"next_page_token": next_page_token},
    }


@router.get("/results", response_model=dict)
async def list_scan_results(
    gmail_account_id: uuid.UUID | None = Query(None),
    is_processed: bool | None = Query(None),
    has_attachments: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await service.list_results_paginated(
        db=db,
        user_id=user.id,
        gmail_account_id=gmail_account_id,
        is_processed=is_processed,
        has_attachments=has_attachments,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [GmailScanResultResponse.model_validate(r) for r in rows],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size else 1,
        },
    }


# ---------------------------------------------------------------------------
# Parse email for import preview
# ---------------------------------------------------------------------------


@router.get("/results/{result_id}/parse", response_model=dict)
async def parse_email_for_import(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    """Parse an email and return suggested import data (vendor, amount, category)."""
    from sqlalchemy import select as sa_select
    from .models import GmailScanResult, GmailAccount

    stmt = (
        sa_select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailScanResult.id == result_id, GmailAccount.user_id == user.id)
    )
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Scan result", str(result_id))

    parsed = service.parse_email_for_import(
        subject=scan_result.subject,
        sender=scan_result.sender,
        body_text=scan_result.body_text,
        email_date=scan_result.date,
    )

    # List attachments info
    attachments = []
    if scan_result.has_attachments:
        attachments.append({"name": "attachment", "has_file": True})

    parsed["attachments"] = attachments

    return {"data": parsed}


# ---------------------------------------------------------------------------
# Import (legacy simple + full flow)
# ---------------------------------------------------------------------------


@router.post("/results/{result_id}/import", response_model=dict)
async def import_attachment(
    result_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    """Legacy: Download attachment only and create Document."""
    settings = _get_settings(request)
    document_id = await service.import_attachment(db, result_id, user, settings)
    return {"data": {"document_id": str(document_id)}}


@router.post("/results/{result_id}/import-full", response_model=dict)
async def import_email_full(
    result_id: uuid.UUID,
    data: EmailImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    """Full import: download attachment + create expense or income record."""
    settings = _get_settings(request)
    result = await service.import_email_full(
        db=db,
        result_id=result_id,
        user=user,
        settings=settings,
        record_type=data.record_type,
        vendor_name=data.vendor_name,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        record_date=data.date,
        category_id=data.category_id,
        income_category=data.income_category,
        notes=data.notes,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Delete scan results
# ---------------------------------------------------------------------------


@router.delete("/results/{result_id}", response_model=dict)
async def delete_scan_result(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.delete_scan_result(db, result_id, user.id)
    return {"data": {"detail": "Scan result deleted"}}


@router.post("/results/bulk-delete", response_model=dict)
async def bulk_delete_scan_results(
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    count = await service.bulk_delete_scan_results(db, data.result_ids, user.id)
    return {"data": {"deleted": count}}


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
