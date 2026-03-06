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
    branding = await service.get_public_branding(db)
    if branding is None:
        return {"data": None}
    return {"data": PublicBrandingResponse.model_validate(branding)}


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
