import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.encryption import get_encryption_service
from app.core.exceptions import ValidationError
from app.dependencies import get_db, require_role
from app.integrations.settings_models import IntegrationConfig

logger = logging.getLogger(__name__)

router = APIRouter()

INTEGRATION_FIELDS = {
    "anthropic": ["api_key"],
    "gemini": ["api_key"],
    "openai": ["api_key"],
    "stripe": ["secret_key", "publishable_key", "webhook_secret"],
    "twilio": ["account_sid", "auth_token", "from_number"],
    "plaid": ["client_id", "secret", "environment"],
    "google": ["client_id", "client_secret"],
    "livekit": ["api_key", "api_secret", "url"],
    "smtp": ["host", "port", "username", "password", "from_email"],
    "cloudflare_r2": ["access_key_id", "secret_access_key", "bucket_name", "endpoint", "account_id"],
    "assemblyai": ["api_key"],
}

SETTINGS_MAP = {
    "anthropic": {
        "api_key": "anthropic_api_key",
    },
    "gemini": {
        "api_key": "gemini_api_key",
    },
    "openai": {
        "api_key": "openai_api_key",
    },
    "stripe": {
        "secret_key": "stripe_secret_key",
        "publishable_key": "stripe_publishable_key",
        "webhook_secret": "stripe_webhook_secret",
    },
    "twilio": {
        "account_sid": "twilio_account_sid",
        "auth_token": "twilio_auth_token",
        "from_number": "twilio_from_number",
    },
    "plaid": {
        "client_id": "plaid_client_id",
        "secret": "plaid_secret",
        "environment": "plaid_env",
    },
    "google": {
        "client_id": "google_client_id",
        "client_secret": "google_client_secret",
    },
    "livekit": {
        "api_key": "livekit_api_key",
        "api_secret": "livekit_api_secret",
        "url": "livekit_url",
    },
    "smtp": {
        "host": "smtp_host",
        "port": "smtp_port",
        "username": "smtp_username",
        "password": "smtp_password",
        "from_email": "smtp_from_email",
    },
    "cloudflare_r2": {
        "access_key_id": "r2_access_key_id",
        "secret_access_key": "r2_secret_access_key",
        "bucket_name": "r2_bucket_name",
        "endpoint": "r2_endpoint",
        "account_id": "cloudflare_account_id",
    },
    "assemblyai": {
        "api_key": "assemblyai_api_key",
    },
}

# Fields that are NOT secrets (shown unmasked and not encrypted)
NON_SECRET_FIELDS = {
    "smtp": {"host", "port", "from_email"},
    "livekit": {"url"},
    "cloudflare_r2": {"bucket_name", "endpoint", "account_id"},
    "plaid": {"environment"},
}


def mask_value(value: str) -> str:
    if not value or len(value) <= 4:
        return "****"
    return "****" + value[-4:]


class IntegrationSettingsUpdate(BaseModel):
    config: dict


@router.get("/settings/{integration_type}")
async def get_integration_settings(
    integration_type: str,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if integration_type not in INTEGRATION_FIELDS:
        raise ValidationError(f"Unknown integration type: {integration_type}")

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.integration_type == integration_type
        )
    )
    config = result.scalar_one_or_none()

    fields = INTEGRATION_FIELDS[integration_type]
    if config is None:
        return {"data": {field: "" for field in fields}, "meta": {"is_configured": False}}

    enc = get_encryption_service()
    decrypted = json.loads(enc.decrypt(config.encrypted_config))

    masked = {}
    has_values = False
    for field in fields:
        val = decrypted.get(field, "")
        if val:
            has_values = True
            masked[field] = mask_value(val)
        else:
            masked[field] = ""

    return {"data": masked, "meta": {"is_configured": has_values}}


@router.put("/settings/{integration_type}")
async def save_integration_settings(
    integration_type: str,
    body: IntegrationSettingsUpdate,
    request: Request,
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if integration_type not in INTEGRATION_FIELDS:
        raise ValidationError(f"Unknown integration type: {integration_type}")

    allowed = set(INTEGRATION_FIELDS[integration_type])
    for key in body.config:
        if key not in allowed:
            raise ValidationError(f"Unknown field: {key}")

    enc = get_encryption_service()

    # Load existing config to merge (don't overwrite with masked values)
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.integration_type == integration_type
        )
    )
    existing = result.scalar_one_or_none()

    existing_config: dict = {}
    if existing:
        existing_config = json.loads(enc.decrypt(existing.encrypted_config))

    # Merge: only update fields that aren't masked placeholders
    new_config = dict(existing_config)
    for key, val in body.config.items():
        if val and not val.startswith("****"):
            new_config[key] = val

    encrypted = enc.encrypt(json.dumps(new_config))

    if existing:
        existing.encrypted_config = encrypted
        existing.updated_by = current_user.id
    else:
        new_record = IntegrationConfig(
            integration_type=integration_type,
            encrypted_config=encrypted,
            updated_by=current_user.id,
        )
        db.add(new_record)

    await db.commit()

    # Update runtime settings so services pick up new values immediately
    mapping = SETTINGS_MAP.get(integration_type, {})
    settings = request.app.state.settings
    for field, setting_attr in mapping.items():
        val = new_config.get(field, "")
        if val:
            setattr(settings, setting_attr, val)

    return {"data": {"message": f"{integration_type} settings saved successfully"}}


async def load_integration_configs(session_factory, settings) -> None:
    """Load saved integration configs from DB and apply to runtime settings on startup."""
    try:
        enc = get_encryption_service()
    except RuntimeError:
        return

    async with session_factory() as db:
        result = await db.execute(select(IntegrationConfig))
        configs = result.scalars().all()
        for config in configs:
            mapping = SETTINGS_MAP.get(config.integration_type, {})
            if not mapping:
                continue
            try:
                decrypted = json.loads(enc.decrypt(config.encrypted_config))
                for field, setting_attr in mapping.items():
                    val = decrypted.get(field, "")
                    if val:
                        setattr(settings, setting_attr, val)
                logger.info("Loaded %s settings from database", config.integration_type)
            except Exception as e:
                logger.warning("Failed to load %s settings: %s", config.integration_type, e)
