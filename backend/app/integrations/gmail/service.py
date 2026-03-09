
from typing import Optional

import base64
import json
import mimetypes
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError, ValidationError

from .models import GmailAccount, GmailScanResult


# ---------------------------------------------------------------------------
# Vendor-to-category mapping (learns from usage patterns)
# ---------------------------------------------------------------------------

VENDOR_CATEGORY_MAP: dict[str, str] = {
    "anthropic": "Software & SaaS",
    "openai": "Software & SaaS",
    "vercel": "Hosting & Infrastructure",
    "aws": "Hosting & Infrastructure",
    "amazon web services": "Hosting & Infrastructure",
    "google cloud": "Hosting & Infrastructure",
    "digitalocean": "Hosting & Infrastructure",
    "dreamhost": "Hosting & Infrastructure",
    "heroku": "Hosting & Infrastructure",
    "github": "Software & SaaS",
    "stripe": "Payment Processing",
    "paypal": "Payment Processing",
    "slack": "Software & SaaS",
    "zoom": "Software & SaaS",
    "microsoft": "Software & SaaS",
    "adobe": "Software & SaaS",
    "figma": "Software & SaaS",
    "notion": "Software & SaaS",
    "canva": "Software & SaaS",
    "twilio": "Communication",
    "mailchimp": "Marketing",
    "hubspot": "Marketing",
    "quickbooks": "Accounting Software",
    "uber": "Travel & Transport",
    "lyft": "Travel & Transport",
    "delta": "Travel & Transport",
    "united airlines": "Travel & Transport",
    "hilton": "Travel & Transport",
    "marriott": "Travel & Transport",
    "staples": "Office Supplies",
    "office depot": "Office Supplies",
    "comcast": "Utilities",
    "verizon": "Utilities",
    "at&t": "Utilities",
    "t-mobile": "Utilities",
}


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------


def _build_flow(settings: Settings):
    """Build a google_auth_oauthlib Flow from app settings."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow


async def get_google_auth_url(user_id: uuid.UUID, settings: Settings) -> str:
    """Generate OAuth2 authorization URL for Gmail."""
    flow = _build_flow(settings)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(user_id),
    )
    return auth_url


async def handle_oauth_callback(
    db: AsyncSession, code: str, state: str, settings: Settings
) -> GmailAccount:
    """Exchange authorization code for tokens, encrypt, and store."""
    from googleapiclient.discovery import build as build_service

    flow = _build_flow(settings)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Retrieve the user's Gmail profile to get their email address
    service = build_service("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "")

    encryption = get_encryption_service()
    encrypted_access = encryption.encrypt(credentials.token)
    encrypted_refresh = encryption.encrypt(credentials.refresh_token or "")

    user_id = uuid.UUID(state)

    # Check if this Gmail account is already connected for this user
    stmt = select(GmailAccount).where(
        GmailAccount.user_id == user_id,
        GmailAccount.email == email,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_access_token = encrypted_access
        existing.encrypted_refresh_token = encrypted_refresh
        existing.token_expiry = credentials.expiry
        existing.scopes = " ".join(credentials.scopes or [])
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    gmail_account = GmailAccount(
        user_id=user_id,
        email=email,
        encrypted_access_token=encrypted_access,
        encrypted_refresh_token=encrypted_refresh,
        token_expiry=credentials.expiry,
        scopes=" ".join(credentials.scopes or []),
        is_active=True,
    )
    db.add(gmail_account)
    await db.commit()
    await db.refresh(gmail_account)
    return gmail_account


# ---------------------------------------------------------------------------
# Authenticated Gmail service builder
# ---------------------------------------------------------------------------


async def _get_gmail_service(gmail_account: GmailAccount, settings: Settings):
    """Build an authenticated Gmail API service, auto-refreshing the token if needed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as build_service

    encryption = get_encryption_service()
    access_token = encryption.decrypt(gmail_account.encrypted_access_token)
    refresh_token = encryption.decrypt(gmail_account.encrypted_refresh_token)

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    # Refresh the token if it has expired
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        # Persist the refreshed tokens
        gmail_account.encrypted_access_token = encryption.encrypt(credentials.token)
        gmail_account.token_expiry = credentials.expiry

    service = build_service("gmail", "v1", credentials=credentials)
    return service


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


async def list_accounts(
    db: AsyncSession, user_id: uuid.UUID
) -> list[GmailAccount]:
    """List all connected Gmail accounts for a user."""
    stmt = select(GmailAccount).where(GmailAccount.user_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def disconnect_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Disconnect (deactivate) a Gmail account."""
    stmt = select(GmailAccount).where(
        GmailAccount.id == account_id,
        GmailAccount.user_id == user_id,
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("Gmail account", "unknown")

    await db.delete(account)
    await db.commit()


# ---------------------------------------------------------------------------
# Email scanning
# ---------------------------------------------------------------------------


def _extract_header(headers: list[dict], name: str) -> str | None:
    """Extract a header value by name from Gmail message headers."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _has_attachments(payload: dict) -> bool:
    """Check recursively whether the message payload has file attachments."""
    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename")
        if filename:
            return True
        if _has_attachments(part):
            return True
    return False


def _extract_body_text(payload: dict) -> str:
    """Extract plain text body from message payload recursively."""
    mime_type = payload.get("mimeType", "")

    # Direct text/plain body
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Multipart — recurse
    parts = payload.get("parts", [])
    for part in parts:
        part_mime = part.get("mimeType", "")
        if part_mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif part_mime.startswith("multipart/"):
            text = _extract_body_text(part)
            if text:
                return text

    # Fall back to text/html if no plain text
    for part in parts:
        if part.get("mimeType", "") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                # Strip HTML tags for a rough text extraction
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()
                return text[:5000]

    return ""


def _extract_body_html(payload: dict) -> str:
    """Extract HTML body from message payload recursively."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        part_mime = part.get("mimeType", "")
        if part_mime == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif part_mime.startswith("multipart/"):
            html = _extract_body_html(part)
            if html:
                return html

    return ""


def _extract_attachment_metadata(payload: dict) -> list[dict]:
    """Extract attachment metadata from payload.

    Handles:
    - Regular attachments (filename + attachmentId)
    - PDF/image MIME parts with empty-string filename (Stripe receipts etc.)
    - Inline/embedded attachments (data in body, no attachmentId)
    - Inline images via CID (no filename, has attachmentId)
    """
    # Skip non-part MIME types that are structural containers
    _SKIP_MIMES = {
        "text/plain", "text/html",
        "multipart/alternative", "multipart/mixed", "multipart/related",
    }

    attachments: list[dict] = []
    parts = payload.get("parts", [])
    for part in parts:
        raw_filename = part.get("filename")  # could be "", None, or actual name
        body = part.get("body", {})
        mime = part.get("mimeType", "application/octet-stream")
        attachment_id = body.get("attachmentId")
        has_inline_data = bool(body.get("data"))
        size = body.get("size", 0)

        # Generate a filename for parts that have none but are real attachments
        filename = raw_filename or ""
        if not filename and attachment_id and mime not in _SKIP_MIMES:
            ext = mimetypes.guess_extension(mime) or ".bin"
            content_id = None
            for h in part.get("headers", []):
                if h.get("name", "").lower() == "content-id":
                    content_id = h.get("value", "").strip("<>")
                    break
            filename = f"attachment_{content_id or uuid.uuid4().hex[:8]}{ext}"

        if not filename and has_inline_data and mime not in _SKIP_MIMES:
            ext = mimetypes.guess_extension(mime) or ".bin"
            filename = f"embedded_{uuid.uuid4().hex[:8]}{ext}"

        # Now decide how to record this attachment
        if filename and attachment_id:
            attachments.append({
                "filename": filename,
                "mimeType": mime,
                "size": size,
                "attachmentId": attachment_id,
            })
        elif filename and has_inline_data:
            raw = body["data"]
            decoded_size = len(base64.urlsafe_b64decode(raw))
            attachments.append({
                "filename": filename,
                "mimeType": mime,
                "size": decoded_size,
                "inline_data": raw,
            })

        # Recurse into nested parts
        attachments.extend(_extract_attachment_metadata(part))
    return attachments


async def scan_emails(
    db: AsyncSession,
    gmail_account_id: uuid.UUID,
    query: str | None,
    max_results: int,
    user: User,
    settings: Settings,
    after_date: date | None = None,
    before_date: date | None = None,
    page_token: str | None = None,
) -> tuple[list[GmailScanResult], str | None]:
    """Search Gmail, save results, and detect attachments.

    Returns (results, next_page_token).
    """
    stmt = select(GmailAccount).where(
        GmailAccount.id == gmail_account_id,
        GmailAccount.user_id == user.id,
        GmailAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    gmail_account = result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account", "inactive")

    service = await _get_gmail_service(gmail_account, settings)

    search_query = query or "has:attachment (invoice OR receipt OR payment)"

    # Add date range filters
    if after_date:
        search_query += f" after:{after_date.isoformat()}"
    if before_date:
        search_query += f" before:{before_date.isoformat()}"

    list_kwargs: dict = {
        "userId": "me",
        "q": search_query,
        "maxResults": max_results,
    }
    if page_token:
        list_kwargs["pageToken"] = page_token

    response = (
        service.users()
        .messages()
        .list(**list_kwargs)
        .execute()
    )

    messages = response.get("messages", [])
    next_page_token = response.get("nextPageToken")
    scan_results: list[GmailScanResult] = []

    import logging
    _log = logging.getLogger(__name__)

    for msg_ref in messages:
        msg_id = msg_ref["id"]

        # Check for existing record — update if missing attachment metadata
        dup_stmt = select(GmailScanResult).where(
            GmailScanResult.message_id == msg_id
        )
        dup_result = await db.execute(dup_stmt)
        existing = dup_result.scalar_one_or_none()
        if existing and existing.attachment_metadata:
            # Already have full metadata — skip
            continue

        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

        headers = msg.get("payload", {}).get("headers", [])
        subject = _extract_header(headers, "Subject")
        sender = _extract_header(headers, "From")
        date_str = _extract_header(headers, "Date")

        parsed_date: Optional[datetime] = None
        if date_str:
            try:
                parsed_date = parsedate_to_datetime(date_str)
            except Exception:
                parsed_date = None

        payload = msg.get("payload", {})
        attachments_found = _has_attachments(payload)
        body_text = _extract_body_text(payload)
        body_html = _extract_body_html(payload)
        att_meta = _extract_attachment_metadata(payload)

        # Download ALL attachments and save to server storage for inline preview
        if att_meta:
            from app.documents.storage import build_storage
            storage = build_storage(settings)
            for att in att_meta:
                try:
                    file_bytes: bytes | None = None

                    # Case 1: Inline data already present (embedded attachment)
                    inline_data = att.pop("inline_data", None)
                    if inline_data:
                        file_bytes = base64.urlsafe_b64decode(inline_data)

                    # Case 2: Regular attachment — fetch from Gmail API
                    att_id = att.get("attachmentId")
                    if not file_bytes and att_id:
                        att_response = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=msg_id, id=att_id)
                            .execute()
                        )
                        raw_data = att_response.get("data", "")
                        if raw_data:
                            file_bytes = base64.urlsafe_b64decode(raw_data)

                    # Verify we got actual data before saving
                    if file_bytes and len(file_bytes) > 0:
                        filename = att.get("filename", "file")
                        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
                        storage_path = await storage.save(file_bytes, ext)
                        att["storage_path"] = storage_path
                        att["size"] = len(file_bytes)
                    else:
                        _log.warning(
                            "Attachment download returned empty data: msg=%s att=%s",
                            msg_id, att.get("filename"),
                        )
                except Exception:
                    _log.exception(
                        "Failed to download attachment: msg=%s att=%s",
                        msg_id, att.get("filename"),
                    )

        # Strip inline_data from metadata before persisting to DB
        # (it's base64 content that would bloat the TEXT column)
        if att_meta:
            for att in att_meta:
                att.pop("inline_data", None)

        if existing:
            # Update existing record with new metadata (rescan backfill)
            existing.body_text = body_text[:5000] if body_text else existing.body_text
            existing.body_html = body_html[:50000] if body_html else existing.body_html
            existing.has_attachments = attachments_found or existing.has_attachments
            existing.attachment_metadata = json.dumps(att_meta) if att_meta else existing.attachment_metadata
            scan_results.append(existing)
            _log.info("Updated existing scan result with attachment metadata: msg=%s", msg_id)
        else:
            # Create new record
            scan_result = GmailScanResult(
                gmail_account_id=gmail_account_id,
                message_id=msg_id,
                subject=subject[:500] if subject else None,
                sender=sender[:255] if sender else None,
                date=parsed_date,
                snippet=msg.get("snippet"),
                body_text=body_text[:5000] if body_text else None,
                body_html=body_html[:50000] if body_html else None,
                has_attachments=attachments_found,
                attachment_metadata=json.dumps(att_meta) if att_meta else None,
                is_processed=False,
            )
            db.add(scan_result)
            scan_results.append(scan_result)

    # Update last sync timestamp
    gmail_account.last_sync_at = datetime.now(timezone.utc)
    await db.commit()

    # Refresh all results so they have generated ids / timestamps
    for sr in scan_results:
        await db.refresh(sr)

    return scan_results, next_page_token


# ---------------------------------------------------------------------------
# List results with pagination
# ---------------------------------------------------------------------------


async def list_results_paginated(
    db: AsyncSession,
    user_id: uuid.UUID,
    gmail_account_id: uuid.UUID | None = None,
    is_processed: bool | None = None,
    has_attachments: bool | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[GmailScanResult], int]:
    """List scan results with filters and pagination. Returns (results, total)."""
    base_stmt = (
        select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailAccount.user_id == user_id)
    )

    if gmail_account_id:
        base_stmt = base_stmt.where(GmailScanResult.gmail_account_id == gmail_account_id)
    if is_processed is not None:
        base_stmt = base_stmt.where(GmailScanResult.is_processed == is_processed)
    if has_attachments is not None:
        base_stmt = base_stmt.where(GmailScanResult.has_attachments == has_attachments)
    if search:
        pattern = f"%{search}%"
        base_stmt = base_stmt.where(
            or_(
                GmailScanResult.subject.ilike(pattern),
                GmailScanResult.sender.ilike(pattern),
                GmailScanResult.snippet.ilike(pattern),
            )
        )

    # Count
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Page
    stmt = (
        base_stmt
        .order_by(GmailScanResult.date.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    return rows, total


# ---------------------------------------------------------------------------
# Delete scan results
# ---------------------------------------------------------------------------


async def delete_scan_result(
    db: AsyncSession,
    result_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a single scan result."""
    stmt = (
        select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailScanResult.id == result_id, GmailAccount.user_id == user_id)
    )
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        raise NotFoundError("Scan result", str(result_id))

    await db.delete(scan_result)
    await db.commit()


async def bulk_delete_scan_results(
    db: AsyncSession,
    result_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Delete multiple scan results. Returns count deleted."""
    stmt = (
        select(GmailScanResult)
        .join(GmailAccount, GmailScanResult.gmail_account_id == GmailAccount.id)
        .where(GmailScanResult.id.in_(result_ids), GmailAccount.user_id == user_id)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    count = 0
    for row in rows:
        await db.delete(row)
        count += 1
    await db.commit()
    return count


# ---------------------------------------------------------------------------
# Email parsing / auto-categorization
# ---------------------------------------------------------------------------


def _parse_amount_from_text(text: str) -> Decimal | None:
    """Try to extract a monetary amount from text.

    Priority: "Total"/"Amount Due"/"Balance Due" lines first, then general $ amounts.
    For general amounts, pick the largest reasonable value (likely the invoice total).
    """
    # High-priority: labeled amounts (total, amount due, balance due, etc.)
    priority_patterns = [
        r"(?:total\s*(?:amount|due|charged?)?|amount\s*due|balance\s*due|grand\s*total|invoice\s*total|payment\s*(?:amount|due))[:\s]*\$?\s*([\d,]+\.?\d{0,2})",
        r"(?:total|amount\s*due|balance\s*due)[:\s]*(?:USD|CAD|EUR|GBP)?\s*\$?\s*([\d,]+\.?\d{0,2})",
    ]
    for pattern in priority_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val = Decimal(match.replace(",", ""))
                if Decimal("0.50") <= val <= Decimal("999999.99"):
                    return val
            except (InvalidOperation, ValueError):
                continue

    # General dollar amounts — pick the largest (likely the total)
    general_patterns = [
        r"\$\s*([\d,]+\.\d{2})",
        r"(?:USD|CAD|EUR|GBP)\s*([\d,]+\.\d{2})",
    ]
    best: Decimal | None = None
    for pattern in general_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val = Decimal(match.replace(",", ""))
                if Decimal("0.50") <= val <= Decimal("999999.99"):
                    if best is None or val > best:
                        best = val
            except (InvalidOperation, ValueError):
                continue
    return best


def _parse_date_from_text(text: str) -> date | None:
    """Try to extract a date from text."""
    # Common date patterns
    patterns = [
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%m/%d/%Y"),
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "%Y-%m-%d"),
        (r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s+(\d{4})", None),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                if fmt:
                    from datetime import datetime as dt
                    parts = match.groups()
                    date_str = "/".join(parts)
                    return dt.strptime(date_str, fmt).date()
                else:
                    # Month name format
                    from datetime import datetime as dt
                    return dt.strptime(match.group(0).replace(",", ""), "%b %d %Y").date()
            except (ValueError, IndexError):
                continue
    return None


def _extract_vendor_from_sender(sender: str | None) -> str | None:
    """Extract vendor name from email sender field."""
    if not sender:
        return None
    # "Vendor Name <email@domain.com>" → "Vendor Name"
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        name = match.group(1).strip()
        if name and not "@" in name:
            return name
    # Plain email: vendor@domain.com → domain
    match = re.search(r"@([\w.-]+)\.", sender)
    if match:
        return match.group(1).replace("-", " ").title()
    return sender.strip()


def _suggest_category(vendor_name: str | None) -> str | None:
    """Suggest an expense category based on vendor name."""
    if not vendor_name:
        return None
    vendor_lower = vendor_name.lower()
    for key, category in VENDOR_CATEGORY_MAP.items():
        if key in vendor_lower:
            return category
    return None


def parse_email_for_import(
    subject: str | None,
    sender: str | None,
    body_text: str | None,
    email_date: datetime | None,
    body_html: str | None = None,
) -> dict:
    """Parse email content and return structured data for import."""
    combined_text = " ".join(filter(None, [subject, body_text or ""]))

    vendor_name = _extract_vendor_from_sender(sender)
    amount = _parse_amount_from_text(combined_text)

    # If no amount found in plain text, try HTML body (often has better structured data)
    if amount is None and body_html:
        html_text = re.sub(r"<[^>]+>", " ", body_html)
        html_text = re.sub(r"\s+", " ", html_text).strip()
        amount = _parse_amount_from_text(html_text)

    parsed_date = _parse_date_from_text(combined_text)

    # Use email date if no date found in body
    if not parsed_date and email_date:
        parsed_date = email_date.date() if isinstance(email_date, datetime) else email_date

    category_suggestion = _suggest_category(vendor_name)

    # Determine if this looks like income (payment received, deposit, etc.)
    income_keywords = ["payment received", "deposit", "credited", "income", "paid you", "transfer received"]
    is_income = any(kw in combined_text.lower() for kw in income_keywords)

    description = subject or "Imported from email"

    return {
        "vendor_name": vendor_name,
        "amount": str(amount) if amount else None,
        "currency": "USD",
        "date": parsed_date.isoformat() if parsed_date else None,
        "description": description[:500] if description else None,
        "category_suggestion": category_suggestion,
        "record_type": "income" if is_income else "expense",
    }


# ---------------------------------------------------------------------------
# Attachment import
# ---------------------------------------------------------------------------


def _find_attachment_parts(payload: dict) -> list[dict]:
    """Recursively find all attachment parts in a message payload."""
    attachments: list[dict] = []
    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename")
        if filename and part.get("body", {}).get("attachmentId"):
            attachments.append(part)
        attachments.extend(_find_attachment_parts(part))
    return attachments


async def import_attachment(
    db: AsyncSession,
    result_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> uuid.UUID:
    """Download an attachment from Gmail and create a Document record."""
    from app.documents.models import Document

    stmt = select(GmailScanResult).where(GmailScanResult.id == result_id)
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        raise NotFoundError("Scan result", str(result_id))

    # Ensure the Gmail account belongs to this user
    acct_stmt = select(GmailAccount).where(
        GmailAccount.id == scan_result.gmail_account_id,
        GmailAccount.user_id == user.id,
    )
    acct_result = await db.execute(acct_stmt)
    gmail_account = acct_result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account", "unknown")

    if not scan_result.has_attachments:
        raise ValidationError("This email has no attachments to import")

    service = await _get_gmail_service(gmail_account, settings)

    # Get the full message to find attachment parts
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=scan_result.message_id, format="full")
        .execute()
    )

    attachment_parts = _find_attachment_parts(msg.get("payload", {}))
    if not attachment_parts:
        raise ValidationError("No downloadable attachments found")

    # Import the first attachment
    part = attachment_parts[0]
    attachment_id = part["body"]["attachmentId"]
    filename = part.get("filename", "attachment")

    att = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=scan_result.message_id, id=attachment_id)
        .execute()
    )

    file_data = base64.urlsafe_b64decode(att["data"])

    # Save to storage
    storage_dir = os.path.join("storage", "documents", str(user.id))
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, f"{uuid.uuid4()}_{filename}")

    with open(file_path, "wb") as f:
        f.write(file_data)

    # Create Document record
    mime_type = (
        part.get("mimeType")
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )

    document = Document(
        user_id=user.id,
        filename=filename,
        file_path=file_path,
        file_size=len(file_data),
        mime_type=mime_type,
        source="gmail",
    )
    db.add(document)

    # Mark scan result as processed and link to document
    scan_result.is_processed = True
    scan_result.matched_document_id = document.id

    await db.commit()
    await db.refresh(document)
    return document.id


# ---------------------------------------------------------------------------
# Full import flow: attachment + expense/income creation
# ---------------------------------------------------------------------------


async def import_email_full(
    db: AsyncSession,
    result_id: uuid.UUID,
    user: User,
    settings: Settings,
    record_type: str = "expense",
    vendor_name: str | None = None,
    description: str | None = None,
    amount: Decimal | None = None,
    currency: str = "USD",
    record_date: date | str | None = None,
    category_id: uuid.UUID | None = None,
    income_category: str | None = None,
    notes: str | None = None,
    account_id: uuid.UUID | None = None,
    is_recurring: bool = False,
    recurring_frequency: str | None = None,
    recurring_next_date: str | None = None,
) -> dict:
    """Import email: download attachment, create expense or income record.

    Returns dict with document_id, expense_id or income_id.
    """
    from app.documents.models import Document
    from app.accounting.models import Expense, ExpenseStatus
    from app.income.models import Income, IncomeCategory

    stmt = select(GmailScanResult).where(GmailScanResult.id == result_id)
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        raise NotFoundError("Scan result", str(result_id))

    if scan_result.is_processed:
        raise ValidationError("This email has already been imported")

    # Ensure the Gmail account belongs to this user
    acct_stmt = select(GmailAccount).where(
        GmailAccount.id == scan_result.gmail_account_id,
        GmailAccount.user_id == user.id,
    )
    acct_result = await db.execute(acct_stmt)
    gmail_account = acct_result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account", "unknown")

    # --- Step 1: Download attachment if present ---
    document_id = None
    if scan_result.has_attachments:
        service = await _get_gmail_service(gmail_account, settings)
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=scan_result.message_id, format="full")
            .execute()
        )
        attachment_parts = _find_attachment_parts(msg.get("payload", {}))
        if attachment_parts:
            part = attachment_parts[0]
            att_id = part["body"]["attachmentId"]
            filename = part.get("filename", "attachment")

            att = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=scan_result.message_id, id=att_id)
                .execute()
            )
            file_data = base64.urlsafe_b64decode(att["data"])

            storage_dir = os.path.join("storage", "documents", str(user.id))
            os.makedirs(storage_dir, exist_ok=True)
            file_path = os.path.join(storage_dir, f"{uuid.uuid4()}_{filename}")

            with open(file_path, "wb") as f:
                f.write(file_data)

            mime_type = (
                part.get("mimeType")
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )

            document = Document(
                user_id=user.id,
                filename=filename,
                file_path=file_path,
                file_size=len(file_data),
                mime_type=mime_type,
                source="gmail",
            )
            db.add(document)
            await db.flush()
            document_id = document.id

    # --- Step 2: Create expense or income record ---
    # Parse date string if needed
    parsed_record_date = None
    if record_date:
        if isinstance(record_date, str):
            try:
                parsed_record_date = date.fromisoformat(record_date)
            except ValueError:
                parsed_record_date = None
        else:
            parsed_record_date = record_date

    use_date = parsed_record_date or (
        scan_result.date.date() if scan_result.date else date.today()
    )
    use_description = description or scan_result.subject or "Imported from email"
    use_amount = amount or Decimal("0.00")

    response_data: dict = {"document_id": str(document_id) if document_id else None}

    if record_type == "income":
        cat = IncomeCategory.OTHER
        if income_category:
            try:
                cat = IncomeCategory(income_category)
            except ValueError:
                pass

        income = Income(
            id=uuid.uuid4(),
            document_id=document_id,
            category=cat,
            description=use_description[:1000],
            amount=use_amount,
            currency=currency,
            date=use_date,
            notes=notes or f"Imported from email: {scan_result.sender}",
            created_by=user.id,
        )
        db.add(income)
        await db.flush()
        scan_result.matched_income_id = income.id
        response_data["income_id"] = str(income.id)
    else:
        expense = Expense(
            id=uuid.uuid4(),
            document_id=document_id,
            category_id=category_id,
            vendor_name=vendor_name,
            description=use_description[:1000],
            amount=use_amount if use_amount > 0 else Decimal("0.01"),
            currency=currency,
            date=use_date,
            status=ExpenseStatus.DRAFT,
            notes=notes or f"Imported from email: {scan_result.sender}",
            user_id=user.id,
        )
        db.add(expense)
        await db.flush()
        scan_result.matched_expense_id = expense.id
        response_data["expense_id"] = str(expense.id)

    # --- Step 3: Create CashbookEntry if account_id provided ---
    cashbook_entry_id = None
    if account_id and use_amount and use_amount > 0:
        try:
            from app.cashbook.schemas import CashbookEntryCreate
            from app.cashbook.service import create_entry
            from app.cashbook.models import EntryType as CashbookEntryType

            entry_type = (
                CashbookEntryType.INCOME if record_type == "income"
                else CashbookEntryType.EXPENSE
            )
            entry_data = CashbookEntryCreate(
                account_id=account_id,
                entry_type=entry_type,
                date=use_date,
                description=use_description[:500],
                total_amount=use_amount,
                category_id=category_id if record_type == "expense" else None,
                notes=notes or f"Email import: {scan_result.sender}",
                source="email_scanner",
                source_id=str(result_id),
            )
            cashbook_entry = await create_entry(db, entry_data, user)
            cashbook_entry_id = str(cashbook_entry.id)
            response_data["cashbook_entry_id"] = cashbook_entry_id
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Email import: cashbook entry creation failed for %s",
                result_id,
                exc_info=True,
            )

    # --- Step 4: Create recurring rule if requested ---
    if is_recurring and recurring_frequency:
        try:
            from app.recurring.models import Frequency, RecurringType
            from app.recurring.schemas import RecurringRuleCreate
            from app.recurring.service import create_rule, advance_date

            freq = Frequency(recurring_frequency)
            rule_type = (
                RecurringType.INCOME if record_type == "income"
                else RecurringType.EXPENSE
            )

            # Next date: provided or auto-calculate from current date
            next_date = use_date
            if recurring_next_date:
                try:
                    next_date = date.fromisoformat(recurring_next_date)
                except ValueError:
                    next_date = advance_date(use_date, freq)
            else:
                next_date = advance_date(use_date, freq)

            template = {
                "vendor_name": vendor_name,
                "description": use_description[:500],
                "amount": str(use_amount),
                "currency": currency,
                "category_id": str(category_id) if category_id else None,
                "account_id": str(account_id) if account_id else None,
                "notes": notes,
            }

            rule_data = RecurringRuleCreate(
                type=rule_type,
                name=f"{vendor_name or use_description[:50]} (recurring)",
                frequency=freq,
                next_run_date=next_date,
                template_data=template,
            )
            rule = await create_rule(db, rule_data, user)
            response_data["recurring_rule_id"] = str(rule.id)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Email import: recurring rule creation failed for %s",
                result_id,
                exc_info=True,
            )

    # --- Step 5: Mark as processed ---
    scan_result.is_processed = True
    if document_id:
        scan_result.matched_document_id = document_id

    await db.commit()
    return response_data


# ---------------------------------------------------------------------------
# Sending email
# ---------------------------------------------------------------------------


async def send_email_via_gmail(
    db: AsyncSession,
    gmail_account_id: uuid.UUID,
    to: str,
    subject: str,
    body_html: str,
    attachments: list[tuple[str, bytes, str]] | None,
    user: User,
    settings: Settings,
) -> None:
    """Send an email through a connected Gmail account using the Gmail API.

    Args:
        attachments: list of (filename, file_bytes, mime_type) tuples.
    """
    stmt = select(GmailAccount).where(
        GmailAccount.id == gmail_account_id,
        GmailAccount.user_id == user.id,
        GmailAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    gmail_account = result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account", "inactive")

    service = await _get_gmail_service(gmail_account, settings)

    # Build MIME message
    if attachments:
        message = MIMEMultipart()
        message.attach(MIMEText(body_html, "html"))

        for filename, file_bytes, mime_type in attachments:
            maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
            mime_part = MIMEBase(maintype, subtype)
            mime_part.set_payload(file_bytes)
            encoders.encode_base64(mime_part)
            mime_part.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
            message.attach(mime_part)
    else:
        message = MIMEText(body_html, "html")

    message["to"] = to
    message["from"] = gmail_account.email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()


# ---------------------------------------------------------------------------
# Background job helper
# ---------------------------------------------------------------------------


async def scan_all_accounts(db: AsyncSession, settings: Settings) -> int:
    """Background job: scan all active Gmail accounts.

    Returns the total number of new scan results found.
    """
    stmt = select(GmailAccount).where(GmailAccount.is_active.is_(True))
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    total_new = 0
    for account in accounts:
        try:
            # Build a minimal User-like object with just the id
            class _UserStub:
                def __init__(self, uid: uuid.UUID):
                    self.id = uid

            user_stub = _UserStub(account.user_id)
            results, _ = await scan_emails(
                db=db,
                gmail_account_id=account.id,
                query=None,
                max_results=50,
                user=user_stub,  # type: ignore[arg-type]
                settings=settings,
            )
            total_new += len(results)
        except Exception:
            # Log but don't fail the entire batch
            continue

    return total_new
