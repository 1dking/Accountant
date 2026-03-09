
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role

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
        body_html=scan_result.body_html,
    )

    # Attachment metadata
    import json as _json
    attachments = []
    if scan_result.attachment_metadata:
        try:
            att_list = _json.loads(scan_result.attachment_metadata)
            for att in att_list:
                attachments.append({
                    "filename": att.get("filename", "attachment"),
                    "mimeType": att.get("mimeType", "application/octet-stream"),
                    "size": att.get("size", 0),
                })
        except Exception:
            if scan_result.has_attachments:
                attachments.append({"filename": "attachment", "mimeType": "unknown", "size": 0})
    elif scan_result.has_attachments:
        attachments.append({"filename": "attachment", "mimeType": "unknown", "size": 0})

    parsed["attachments"] = attachments
    parsed["body_html"] = scan_result.body_html
    parsed["body_text"] = scan_result.body_text

    return {"data": parsed}


# ---------------------------------------------------------------------------
# Attachment preview (stream from storage for inline PDF/image display)
# ---------------------------------------------------------------------------


@router.get("/results/{result_id}/attachment/{attachment_index}")
async def get_attachment_preview(
    result_id: uuid.UUID,
    attachment_index: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_token),
):
    """Stream a pre-downloaded attachment for inline preview.

    Accepts auth via Bearer header or ?token= query parameter
    so it can be used in <iframe> and <img> tags.
    """
    import json as _json
    from .models import GmailScanResult, GmailAccount
    from app.documents.storage import build_storage

    stmt = (
        select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailScanResult.id == result_id, GmailAccount.user_id == user.id)
    )
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Scan result", str(result_id))

    if not scan_result.attachment_metadata:
        from app.core.exceptions import ValidationError
        raise ValidationError("No attachment metadata available")

    att_list = _json.loads(scan_result.attachment_metadata)
    if attachment_index < 0 or attachment_index >= len(att_list):
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Attachment index {attachment_index} out of range")

    att = att_list[attachment_index]
    storage_path = att.get("storage_path")
    filename = att.get("filename", "attachment")
    mime_type = att.get("mimeType", "application/octet-stream")

    settings = _get_settings(request)
    storage = build_storage(settings)

    # Prefer pre-downloaded file from storage
    if storage_path and await storage.exists(storage_path):
        from app.documents.storage import LocalStorage
        if isinstance(storage, LocalStorage):
            full_path = storage.get_full_path(storage_path)
            return FileResponse(
                path=str(full_path),
                media_type=mime_type,
                filename=filename,
                headers={"Content-Disposition": f'inline; filename="{filename}"'},
            )
        else:
            # R2 or other — read bytes and return
            from fastapi.responses import Response
            data = await storage.read(storage_path)
            return Response(
                content=data,
                media_type=mime_type,
                headers={"Content-Disposition": f'inline; filename="{filename}"'},
            )

    # Fallback: download from Gmail API on-demand (for older scan results)
    attachment_id = att.get("attachmentId")
    if not attachment_id:
        from app.core.exceptions import ValidationError
        raise ValidationError("Attachment not available — re-scan to download")

    acct_stmt = select(GmailAccount).where(
        GmailAccount.id == scan_result.gmail_account_id,
        GmailAccount.user_id == user.id,
    )
    acct_result = await db.execute(acct_stmt)
    gmail_account = acct_result.scalar_one_or_none()
    if not gmail_account:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Gmail account", "unknown")

    gmail_service = await service._get_gmail_service(gmail_account, settings)

    import base64
    att_response = (
        gmail_service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=scan_result.message_id, id=attachment_id)
        .execute()
    )
    raw_data = att_response.get("data", "")
    file_bytes = base64.urlsafe_b64decode(raw_data) if raw_data else b""

    # Save to storage for next time
    if file_bytes:
        try:
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
            saved_path = await storage.save(file_bytes, ext)
            att["storage_path"] = saved_path
            att["size"] = len(file_bytes)
            scan_result.attachment_metadata = _json.dumps(att_list)
            await db.commit()
        except Exception:
            pass

    from fastapi.responses import Response
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


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
        account_id=data.account_id,
        is_recurring=data.is_recurring,
        recurring_frequency=data.recurring_frequency,
        recurring_next_date=data.recurring_next_date,
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
