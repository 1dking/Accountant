"""FastAPI router for universal branding settings."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.branding import service
from app.branding.schemas import BrandingResponse, BrandingUpdate, PublicBrandingResponse
from app.dependencies import get_current_user, get_db, require_role
from app.documents.storage import LocalStorage, StorageBackend

router = APIRouter()


def _get_storage(request: Request) -> StorageBackend:
    """Local-disk storage for brand logos. Mirrors the company-logo
    pattern in settings/router.py — we always store branding assets
    on the VPS's local disk so the public GET endpoint can stream
    them without needing R2 public-access configured."""
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)

ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "svg", "webp"}
LOGO_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
    "webp": "image/webp",
}


@router.get("/public")
async def get_public_branding(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public (no-auth) branding payload — used by sign-in, knock, and
    other guest surfaces. Folds in CompanySettings.company_name so the
    org name shows up correctly without requiring auth."""
    from app.settings.service import get_company_settings

    branding = await service.get_public_branding(db)
    company = await get_company_settings(db)
    if branding is None and company is None:
        return {"data": None}

    if branding is not None:
        payload = PublicBrandingResponse.model_validate(branding)
    else:
        # Mint a defaults-only response when no BrandingSettings row
        # exists yet but a CompanySettings row does (e.g. fresh install
        # that only ran the company-info onboarding).
        payload = PublicBrandingResponse(
            primary_color="#2563eb",
            secondary_color="#64748b",
            accent_color="#f59e0b",
            font_heading="Inter",
            font_body="Inter",
            border_radius="8px",
        )
    if company is not None and company.company_name:
        payload.org_name = company.company_name
    # Commit 27 — if the admin only uploaded a Company Logo (the old
    # /settings/company/logo path) and didn't set a separate Brand Logo,
    # fall through to the company logo so guest surfaces still show a
    # branded image. The /settings/company/logo endpoint is publicly
    # readable (it streams from disk without an auth check).
    if not payload.logo_url and company is not None and company.logo_storage_path:
        payload.logo_url = "/api/settings/company/logo"
    return {"data": payload}


@router.get("")
async def get_branding(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    branding = await service.get_or_create_branding(db, current_user.id)
    return {"data": BrandingResponse.model_validate(branding)}


@router.put("")
async def update_branding(
    data: BrandingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    branding = await service.update_branding(db, data, current_user)
    return {"data": BrandingResponse.model_validate(branding)}


@router.post("/logo", status_code=201)
async def upload_brand_logo(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    file: UploadFile = File(...),
) -> dict:
    """Commit 28 — upload a brand logo file. Stores bytes via the
    storage backend (local disk on VPS), records the storage path on
    BrandingSettings.logo_storage_path, and rewrites logo_url to
    /api/branding/logo so guest surfaces hit our public GET endpoint
    (which streams the bytes back).

    Previously we tried to push directly to R2 and stuffed the R2
    endpoint URL into logo_url — but R2 endpoint URLs aren't publicly
    fetchable without a custom domain configured, so the logo never
    loaded. Streaming through the backend sidesteps that entirely.

    Accountant + admin can upload.
    """
    storage = _get_storage(request)

    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid file type '.{extension}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_LOGO_EXTENSIONS))}"
            ),
        )

    body = await file.read()
    if not body:
        raise HTTPException(status_code=422, detail="Empty file.")
    if len(body) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Logo must be under 5 MB.")

    # Clean up the previous logo if there is one (best-effort).
    previous = await service.get_branding(db)
    if previous and previous.logo_storage_path:
        try:
            await storage.delete(previous.logo_storage_path)
        except Exception:
            pass

    storage_path = await storage.save(body, extension)
    # Cache-bust the public URL with a timestamp so browsers refresh
    # immediately after re-upload instead of holding onto a stale image.
    public_url = f"/api/branding/logo?v={int(time.time())}"
    update = BrandingUpdate(
        logo_url=public_url,
        logo_storage_path=storage_path,
    )
    branding = await service.update_branding(db, update, current_user)
    return {"data": BrandingResponse.model_validate(branding)}


@router.get("/logo")
async def serve_brand_logo(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Public (no-auth) brand-logo bytes. Streams from the storage
    backend; mirrors /api/settings/company/logo so the sidebar, login
    page, and guest knock surfaces can embed it via <img src>."""
    storage = _get_storage(request)
    branding = await service.get_public_branding(db)
    if not branding or not branding.logo_storage_path:
        raise HTTPException(status_code=404, detail="No brand logo uploaded")
    data = await storage.read(branding.logo_storage_path)
    extension = branding.logo_storage_path.rsplit(".", 1)[-1].lower()
    content_type = LOGO_CONTENT_TYPES.get(extension, "application/octet-stream")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )
