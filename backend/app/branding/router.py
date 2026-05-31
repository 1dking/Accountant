"""FastAPI router for universal branding settings."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.branding import service
from app.branding.schemas import BrandingResponse, BrandingUpdate, PublicBrandingResponse
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()

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
    """Commit 27 — upload a brand logo file. Uploads to R2 (or local
    fallback in dev), writes the resulting public URL onto
    BrandingSettings.logo_url, and returns the updated row.

    This avoids forcing the admin to host the logo elsewhere just to
    paste a URL. Accountant + admin can upload.
    """
    from app.pages.publisher import upload_bytes_to_r2

    settings = request.app.state.settings
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

    key = f"branding/logo-{uuid.uuid4().hex[:12]}.{extension}"
    content_type = LOGO_CONTENT_TYPES.get(extension, "application/octet-stream")
    public_url = await upload_bytes_to_r2(settings, key, body, content_type)

    update = BrandingUpdate(logo_url=public_url)
    branding = await service.update_branding(db, update, current_user)
    return {"data": BrandingResponse.model_validate(branding)}
