
import base64
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError, ValidationError

from .models import GmailAccount, GmailScanResult


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
        raise NotFoundError("Gmail account not found")

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


async def scan_emails(
    db: AsyncSession,
    gmail_account_id: uuid.UUID,
    query: str | None,
    max_results: int,
    user: User,
    settings: Settings,
) -> list[GmailScanResult]:
    """Search Gmail, save results, and detect attachments."""
    stmt = select(GmailAccount).where(
        GmailAccount.id == gmail_account_id,
        GmailAccount.user_id == user.id,
        GmailAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    gmail_account = result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account not found or inactive")

    service = await _get_gmail_service(gmail_account, settings)

    search_query = query or "has:attachment (invoice OR receipt OR payment)"
    response = (
        service.users()
        .messages()
        .list(userId="me", q=search_query, maxResults=max_results)
        .execute()
    )

    messages = response.get("messages", [])
    scan_results: list[GmailScanResult] = []

    for msg_ref in messages:
        msg_id = msg_ref["id"]

        # Skip duplicates
        dup_stmt = select(GmailScanResult).where(
            GmailScanResult.message_id == msg_id
        )
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
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

        parsed_date: datetime | None = None
        if date_str:
            try:
                parsed_date = parsedate_to_datetime(date_str)
            except Exception:
                parsed_date = None

        attachments_found = _has_attachments(msg.get("payload", {}))

        scan_result = GmailScanResult(
            gmail_account_id=gmail_account_id,
            message_id=msg_id,
            subject=subject[:500] if subject else None,
            sender=sender[:255] if sender else None,
            date=parsed_date,
            snippet=msg.get("snippet"),
            has_attachments=attachments_found,
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

    return scan_results


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
        raise NotFoundError("Scan result not found")

    # Ensure the Gmail account belongs to this user
    acct_stmt = select(GmailAccount).where(
        GmailAccount.id == scan_result.gmail_account_id,
        GmailAccount.user_id == user.id,
    )
    acct_result = await db.execute(acct_stmt)
    gmail_account = acct_result.scalar_one_or_none()
    if not gmail_account:
        raise NotFoundError("Gmail account not found")

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
        raise NotFoundError("Gmail account not found or inactive")

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
            results = await scan_emails(
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
