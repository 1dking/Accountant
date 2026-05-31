"""FastAPI router for universal branding settings."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.branding import service
from app.branding.schemas import BrandingResponse, BrandingUpdate, PublicBrandingResponse
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


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
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    branding = await service.update_branding(db, data, current_user)
    return {"data": BrandingResponse.model_validate(branding)}
