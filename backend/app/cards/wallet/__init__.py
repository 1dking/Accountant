"""Apple/Google Wallet passes for business cards.

Credentials live in IntegrationConfig rows ("apple_wallet" /
"google_wallet"), encrypted at rest — read directly here rather than
mirrored onto the global Settings() singleton, because nothing outside
this package needs cert blobs.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import get_encryption_service
from app.integrations.settings_models import IntegrationConfig

logger = logging.getLogger(__name__)

APPLE_WALLET = "apple_wallet"
GOOGLE_WALLET = "google_wallet"


async def load_wallet_config(db: AsyncSession, integration_type: str) -> dict | None:
    """Decrypt an IntegrationConfig row into a plain dict, or None."""
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.integration_type == integration_type
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    try:
        enc = get_encryption_service()
        config = json.loads(enc.decrypt(row.encrypted_config))
        return config if isinstance(config, dict) else None
    except Exception:  # noqa: BLE001 — a corrupt config reads as unconfigured
        logger.exception("Failed to decrypt %s config", integration_type)
        return None
