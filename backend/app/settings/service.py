"""Business logic for the company settings module."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.documents.storage import StorageBackend
from app.settings.models import CompanySettings
from app.settings.schemas import CompanySettingsUpdate

logger = logging.getLogger(__name__)


async def get_company_settings(db: AsyncSession) -> CompanySettings | None:
    """Return the singleton company settings row, or None if not yet created."""
    result = await db.execute(
        select(CompanySettings).options(
            selectinload(CompanySettings.default_tax_rate)
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_company_settings(
    db: AsyncSession, user: User
) -> CompanySettings:
    """Return existing company settings or create a default row."""
    settings = await get_company_settings(db)
    if settings is None:
        settings = CompanySettings(created_by=user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_company_settings(
    db: AsyncSession, data: CompanySettingsUpdate, user: User
) -> CompanySettings:
    """Apply a partial update to company settings."""
    settings = await get_or_create_company_settings(db, user)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return settings


async def upload_logo(
    db: AsyncSession,
    file_data: bytes,
    extension: str,
    storage: StorageBackend,
    user: User,
) -> CompanySettings:
    """Save a new company logo, replacing the previous one if it exists."""
    settings = await get_or_create_company_settings(db, user)

    # Delete old logo if present
    if settings.logo_storage_path:
        try:
            await storage.delete(settings.logo_storage_path)
        except Exception:
            logger.warning(
                "Failed to delete old logo at %s", settings.logo_storage_path
            )

    # Save new logo
    storage_path = await storage.save(file_data, extension)
    settings.logo_storage_path = storage_path
    await db.commit()
    await db.refresh(settings)
    return settings


async def delete_logo(
    db: AsyncSession, storage: StorageBackend, user: User
) -> CompanySettings:
    """Remove the current company logo."""
    settings = await get_or_create_company_settings(db, user)

    if settings.logo_storage_path:
        try:
            await storage.delete(settings.logo_storage_path)
        except Exception:
            logger.warning(
                "Failed to delete logo at %s", settings.logo_storage_path
            )
        settings.logo_storage_path = None
        await db.commit()
        await db.refresh(settings)

    return settings


async def get_logo_bytes(
    db: AsyncSession, storage: StorageBackend
) -> tuple[bytes, str] | None:
    """Read the logo file from storage.

    Returns a (bytes, extension) tuple, or None if no logo is configured.
    """
    settings = await get_company_settings(db)
    if not settings or not settings.logo_storage_path:
        return None
    data = await storage.read(settings.logo_storage_path)
    ext = settings.logo_storage_path.rsplit(".", 1)[-1].lower()
    return data, ext
