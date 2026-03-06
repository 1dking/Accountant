"""Business logic for universal branding settings."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.branding.models import BrandingSettings


async def get_branding(db: AsyncSession) -> BrandingSettings | None:
    """Get the singleton branding settings row."""
    result = await db.execute(select(BrandingSettings).limit(1))
    return result.scalar_one_or_none()


async def get_or_create_branding(db: AsyncSession, user_id: uuid.UUID) -> BrandingSettings:
    """Get or create the singleton branding settings."""
    branding = await get_branding(db)
    if branding is None:
        branding = BrandingSettings(
            id=uuid.uuid4(),
            updated_by=user_id,
        )
        db.add(branding)
        await db.commit()
        await db.refresh(branding)
    return branding


async def update_branding(db: AsyncSession, data, user) -> BrandingSettings:
    """Update branding settings."""
    branding = await get_or_create_branding(db, user.id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(branding, field, value)
    branding.updated_by = user.id
    await db.commit()
    await db.refresh(branding)
    return branding


async def get_public_branding(db: AsyncSession) -> BrandingSettings | None:
    """Get branding for public pages (no auth required)."""
    return await get_branding(db)
