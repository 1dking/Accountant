"""FastAPI router for the company settings module."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.documents.storage import LocalStorage, StorageBackend
from app.settings.schemas import CompanySettingsResponse, CompanySettingsUpdate
from app.settings.service import (
    delete_logo,
    get_logo_bytes,
    get_or_create_company_settings,
    update_company_settings,
    upload_logo,
)

router = APIRouter()

# Allowed image extensions for logo upload
ALLOWED_LOGO_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "svg", "webp"}

# Map file extension to MIME type
EXTENSION_CONTENT_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
    "webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Dependency: storage backend
# ---------------------------------------------------------------------------


def get_storage(request: Request) -> StorageBackend:
    """Resolve the storage backend from application settings."""
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return company settings (creates default row if none exists)."""
    settings = await get_or_create_company_settings(db, current_user)
    return {"data": CompanySettingsResponse.model_validate(settings)}


@router.put("/")
async def update_settings(
    data: CompanySettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update company settings (accountant/admin only)."""
    settings = await update_company_settings(db, data, current_user)
    return {"data": CompanySettingsResponse.model_validate(settings)}


@router.post("/logo", status_code=201)
async def upload_logo_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
) -> dict:
    """Upload a company logo image (accountant/admin only).

    Accepted formats: png, jpg, jpeg, svg, webp.
    """
    # Determine extension from filename
    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type '.{extension}'. Allowed: {', '.join(sorted(ALLOWED_LOGO_EXTENSIONS))}",
        )

    file_data = await file.read()
    settings = await upload_logo(db, file_data, extension, storage, current_user)
    return {"data": CompanySettingsResponse.model_validate(settings)}


@router.delete("/logo")
async def delete_logo_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Remove the company logo (accountant/admin only)."""
    settings = await delete_logo(db, storage, current_user)
    return {"data": CompanySettingsResponse.model_validate(settings)}


@router.get("/logo")
async def get_logo(
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> Response:
    """Serve the company logo image.

    No authentication required -- the logo needs to be embeddable in
    PDFs, emails, and public-facing invoice pages.
    """
    result = await get_logo_bytes(db, storage)
    if result is None:
        raise HTTPException(status_code=404, detail="No logo uploaded")

    data, ext = result
    content_type = EXTENSION_CONTENT_TYPES.get(ext, "application/octet-stream")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )
