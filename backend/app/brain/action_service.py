"""Service for executing O-Brain pending actions (email, SMS, docs, drive)."""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.brain.models import BrainPendingAction, PendingActionStatus
from app.config import Settings

logger = logging.getLogger(__name__)


async def _get_action(
    db: AsyncSession, action_id: uuid.UUID, user: User,
) -> BrainPendingAction | None:
    stmt = select(BrainPendingAction).where(
        and_(
            BrainPendingAction.id == action_id,
            BrainPendingAction.user_id == user.id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def execute_pending_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    user: User,
) -> dict:
    """Execute a pending action after user confirmation."""
    action = await _get_action(db, action_id, user)
    if not action:
        from fastapi import HTTPException
        raise HTTPException(404, "Action not found")

    if action.status != PendingActionStatus.PENDING:
        return {"error": f"Action already {action.status.value}"}

    data = json.loads(action.data_json)
    action_type = action.action_type.value
    settings = Settings()

    try:
        if action_type == "send_email":
            result = await _execute_send_email(db, user, data, settings)
        elif action_type == "send_sms":
            result = await _execute_send_sms(db, user, data, settings)
        elif action_type == "create_document":
            result = await _execute_create_document(db, user, data, settings)
        elif action_type == "save_to_drive":
            result = await _execute_save_to_drive(db, user, data, settings)
        else:
            return {"error": f"Unknown action type: {action_type}"}

        action.status = PendingActionStatus.EXECUTED
        action.executed_at = datetime.now(timezone.utc)
        action.result_json = json.dumps(result)
        await db.commit()

        logger.info("Executed action %s (%s) for user %s", action_id, action_type, user.id)
        return {"status": "executed", "action_type": action_type, **result}

    except Exception as e:
        logger.exception("Failed to execute action %s", action_id)
        return {"error": str(e)[:500]}


async def cancel_pending_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    user: User,
) -> dict:
    action = await _get_action(db, action_id, user)
    if not action:
        from fastapi import HTTPException
        raise HTTPException(404, "Action not found")

    if action.status != PendingActionStatus.PENDING:
        return {"error": f"Action already {action.status.value}"}

    action.status = PendingActionStatus.CANCELLED
    await db.commit()
    return {"status": "cancelled"}


async def update_pending_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    user: User,
    new_data: dict,
) -> dict:
    action = await _get_action(db, action_id, user)
    if not action:
        from fastapi import HTTPException
        raise HTTPException(404, "Action not found")

    if action.status != PendingActionStatus.PENDING:
        return {"error": f"Action already {action.status.value}"}

    # Merge new data into existing
    existing = json.loads(action.data_json)
    existing.update(new_data)
    action.data_json = json.dumps(existing)
    await db.commit()
    return {"status": "updated", "data": existing}


# ---------------------------------------------------------------------------
# Execution handlers
# ---------------------------------------------------------------------------


async def _execute_send_email(
    db: AsyncSession, user: User, data: dict, settings: Settings,
) -> dict:
    """Send email via SMTP or Gmail."""
    to = data["to"]
    subject = data["subject"]
    body = data.get("body", "")

    # Try Gmail first (connected accounts)
    try:
        from app.integrations.gmail.models import GmailAccount
        stmt = select(GmailAccount).where(
            and_(GmailAccount.user_id == user.id, GmailAccount.is_active == True)  # noqa: E712
        ).limit(1)
        result = await db.execute(stmt)
        gmail = result.scalar_one_or_none()

        if gmail:
            from app.integrations.gmail.service import send_email_via_gmail
            await send_email_via_gmail(db, gmail.id, to, subject, body, None, user, settings)
            return {"sent_via": "gmail", "to": to, "subject": subject}
    except Exception as e:
        logger.warning("Gmail send failed, trying SMTP: %s", e)

    # Fallback to SMTP
    try:
        from app.email.models import SmtpConfig
        smtp_stmt = select(SmtpConfig).where(
            and_(SmtpConfig.created_by == user.id, SmtpConfig.is_default == True)  # noqa: E712
        ).limit(1)
        smtp_result = await db.execute(smtp_stmt)
        smtp = smtp_result.scalar_one_or_none()

        if not smtp:
            # Try any SMTP config
            smtp_result = await db.execute(
                select(SmtpConfig).where(SmtpConfig.created_by == user.id).limit(1)
            )
            smtp = smtp_result.scalar_one_or_none()

        if smtp:
            from app.email.service import send_email
            await send_email(smtp, to, subject, body)
            return {"sent_via": "smtp", "to": to, "subject": subject}
    except Exception as e:
        logger.warning("SMTP send failed: %s", e)

    raise RuntimeError("No email account configured. Connect Gmail or add SMTP in Settings.")


async def _execute_send_sms(
    db: AsyncSession, user: User, data: dict, settings: Settings,
) -> dict:
    """Send SMS via Twilio."""
    from app.integrations.twilio.service import send_sms

    to = data["to"]
    message = data["message"]

    sms_log = await send_sms(db, to, message, user, settings)
    return {
        "sent": True,
        "to": to,
        "message": message,
        "char_count": len(message),
        "sms_id": str(sms_log.id),
    }


async def _execute_create_document(
    db: AsyncSession, user: User, data: dict, settings: Settings,
) -> dict:
    """Create a document in the Drive/Docs system."""
    from app.documents.service import upload_document
    from app.documents.storage import build_storage

    title = data["title"]
    content = data.get("content", "")

    # Save as HTML document
    filename = f"{title}.html"
    file_data = content.encode("utf-8")
    storage = build_storage(settings)

    doc = await upload_document(
        db, storage, file_data, filename, "text/html",
        user, folder_id=None, settings=settings,
        document_type="other", title=title,
    )

    return {
        "created": True,
        "document_id": str(doc.id),
        "title": title,
        "navigate_to": f"/documents/{doc.id}",
    }


async def _execute_save_to_drive(
    db: AsyncSession, user: User, data: dict, settings: Settings,
) -> dict:
    """Save a file to Drive."""
    from app.documents.service import upload_document
    from app.documents.storage import build_storage

    filename = data["filename"]
    content = data.get("content", "")
    folder_name = data.get("folder", "")

    # Resolve folder
    folder_id = None
    if folder_name:
        from app.documents.models import Folder
        stmt = select(Folder).where(
            and_(Folder.created_by == user.id, Folder.name.ilike(f"%{folder_name}%"))
        ).limit(1)
        result = await db.execute(stmt)
        folder = result.scalar_one_or_none()
        if folder:
            folder_id = folder.id

    # Determine MIME type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    mime_map = {
        "html": "text/html", "htm": "text/html",
        "txt": "text/plain", "md": "text/markdown",
        "json": "application/json", "csv": "text/csv",
        "xml": "application/xml",
    }
    mime_type = mime_map.get(ext, "text/plain")

    file_data = content.encode("utf-8")
    storage = build_storage(settings)

    doc = await upload_document(
        db, storage, file_data, filename, mime_type,
        user, folder_id=folder_id, settings=settings,
        document_type="other", title=filename,
    )

    return {
        "saved": True,
        "document_id": str(doc.id),
        "filename": filename,
        "folder": folder_name or "Root",
        "navigate_to": f"/documents/{doc.id}",
    }
