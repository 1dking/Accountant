"""Smart Import API router."""

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_current_user_or_token, get_db
from app.smart_import import service
from app.smart_import.schemas import (
    ImportConfirmRequest,
    ImportItemUpdate,
    SmartImportDetailResponse,
    SmartImportItemResponse,
    SmartImportResponse,
)
from app.config import Settings

router = APIRouter()
settings = Settings()


@router.post("/upload", status_code=201)
async def upload_for_import(
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Upload a file for smart import. AI processing runs in background."""
    from app.core.exceptions import ValidationError as AppValidationError

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise AppValidationError("File too large. Maximum size is 20MB.")

    allowed_types = {
        "image/png", "image/jpeg", "image/webp", "image/gif",
        "application/pdf",
    }
    if file.content_type not in allowed_types:
        raise AppValidationError(
            f"Unsupported file type: {file.content_type}. "
            "Supported: images (PNG, JPEG, WebP, GIF) and PDF."
        )

    # Save file
    file_id = uuid.uuid4()
    upload_dir = os.path.join(settings.storage_path, "smart_imports")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "file")[1]
    storage_path = f"smart_imports/{file_id}{ext}"
    full_path = os.path.join(settings.storage_path, storage_path)

    with open(full_path, "wb") as f:
        f.write(contents)

    # Create import record
    imp = await service.create_import(
        db, user,
        filename=file.filename or "file",
        storage_path=storage_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(contents),
    )

    # Process with AI (synchronous for now — could be background)
    imp = await service.process_import(
        db, imp.id, contents, file.content_type or "application/octet-stream"
    )

    return {
        "data": SmartImportDetailResponse(
            id=str(imp.id),
            original_filename=imp.original_filename,
            mime_type=imp.mime_type,
            file_size=imp.file_size,
            status=imp.status,
            document_type=imp.document_type,
            ai_summary=imp.ai_summary,
            error_message=imp.error_message,
            processing_time_ms=imp.processing_time_ms,
            item_count=len(imp.items),
            created_at=imp.created_at.isoformat(),
            items=[
                SmartImportItemResponse(
                    id=str(item.id),
                    status=item.status,
                    entry_type=item.entry_type,
                    date=item.date,
                    description=item.description,
                    amount=item.amount,
                    tax_amount=item.tax_amount,
                    category_suggestion=item.category_suggestion,
                    confidence=item.confidence,
                    is_duplicate=item.is_duplicate,
                    duplicate_entry_id=str(item.duplicate_entry_id) if item.duplicate_entry_id else None,
                    cashbook_entry_id=str(item.cashbook_entry_id) if item.cashbook_entry_id else None,
                )
                for item in imp.items
            ],
        )
    }


@router.get("")
async def list_imports(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """List user's smart imports."""
    imports = await service.list_imports(db, user.id)
    return {
        "data": [
            SmartImportResponse(
                id=str(imp.id),
                original_filename=imp.original_filename,
                mime_type=imp.mime_type,
                file_size=imp.file_size,
                status=imp.status,
                document_type=imp.document_type,
                ai_summary=imp.ai_summary,
                error_message=imp.error_message,
                processing_time_ms=imp.processing_time_ms,
                item_count=len(imp.items),
                created_at=imp.created_at.isoformat(),
            )
            for imp in imports
        ]
    }


@router.get("/{import_id}")
async def get_import(
    import_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Get a smart import with items."""
    imp = await service.get_import(db, import_id, user.id)
    return {
        "data": SmartImportDetailResponse(
            id=str(imp.id),
            original_filename=imp.original_filename,
            mime_type=imp.mime_type,
            file_size=imp.file_size,
            status=imp.status,
            document_type=imp.document_type,
            ai_summary=imp.ai_summary,
            error_message=imp.error_message,
            processing_time_ms=imp.processing_time_ms,
            item_count=len(imp.items),
            created_at=imp.created_at.isoformat(),
            items=[
                SmartImportItemResponse(
                    id=str(item.id),
                    status=item.status,
                    entry_type=item.entry_type,
                    date=item.date,
                    description=item.description,
                    amount=item.amount,
                    tax_amount=item.tax_amount,
                    category_suggestion=item.category_suggestion,
                    confidence=item.confidence,
                    is_duplicate=item.is_duplicate,
                    duplicate_entry_id=str(item.duplicate_entry_id) if item.duplicate_entry_id else None,
                    cashbook_entry_id=str(item.cashbook_entry_id) if item.cashbook_entry_id else None,
                )
                for item in imp.items
            ],
        )
    }


@router.get("/{import_id}/preview")
async def preview_import_file(
    import_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_or_token)],
):
    """Serve the uploaded file for inline preview (PDF iframe / image tag)."""
    imp = await service.get_import(db, import_id, user.id)
    full_path = os.path.join(settings.storage_path, imp.storage_path)
    if not os.path.exists(full_path):
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Import file", str(import_id))
    return FileResponse(
        path=full_path,
        media_type=imp.mime_type,
        filename=imp.original_filename,
        headers={"Content-Disposition": f'inline; filename="{imp.original_filename}"'},
    )


@router.put("/items/{item_id}")
async def update_import_item(
    item_id: uuid.UUID,
    data: ImportItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Update a single import item (approve, reject, edit)."""
    updates = data.model_dump(exclude_unset=True)
    item = await service.update_item(db, item_id, user.id, **updates)
    return {
        "data": SmartImportItemResponse(
            id=str(item.id),
            status=item.status,
            entry_type=item.entry_type,
            date=item.date,
            description=item.description,
            amount=item.amount,
            tax_amount=item.tax_amount,
            category_suggestion=item.category_suggestion,
            confidence=item.confidence,
            is_duplicate=item.is_duplicate,
            duplicate_entry_id=str(item.duplicate_entry_id) if item.duplicate_entry_id else None,
            cashbook_entry_id=str(item.cashbook_entry_id) if item.cashbook_entry_id else None,
        )
    }


@router.post("/{import_id}/confirm")
async def confirm_import(
    import_id: uuid.UUID,
    data: ImportConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Confirm and create cashbook entries from import items."""
    item_uuids = [uuid.UUID(i) for i in data.item_ids] if data.item_ids else None
    result = await service.confirm_import(
        db, import_id, user.id, uuid.UUID(data.account_id), item_uuids
    )
    return {"data": result}


@router.delete("/{import_id}", status_code=204)
async def delete_import(
    import_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Delete an import batch and its associated cashbook entries."""
    await service.delete_import(db, import_id, user.id)


@router.delete("/items/{item_id}", status_code=204)
async def delete_import_item(
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Delete a single import item from review."""
    await service.delete_item(db, item_id, user.id)
