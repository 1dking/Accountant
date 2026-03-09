"""API endpoints for platform administration."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db
from app.platform_admin import schemas, service

router = APIRouter()


# ── Access control ───────────────────────────────────────────────────────

async def require_platform_admin(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Only allow admins or emails listed in SUPER_ADMIN_EMAILS."""
    settings = request.app.state.settings
    super_emails_raw = getattr(settings, "super_admin_emails", "")
    super_emails = [e.strip().lower() for e in super_emails_raw.split(",") if e.strip()]

    is_super = current_user.email.lower() in super_emails
    is_admin = current_user.role == Role.ADMIN

    if not is_super and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return current_user


# ── Dashboard ────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard_metrics(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    metrics = await service.get_dashboard_metrics(db)
    return {"data": metrics}


# ── Feature flags ────────────────────────────────────────────────────────

@router.get("/feature-flags")
async def list_feature_flags(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    flags = await service.list_feature_flags(db)
    return {"data": [schemas.FeatureFlagResponse.model_validate(f) for f in flags]}


@router.post("/feature-flags", status_code=201)
async def create_feature_flag(
    body: schemas.FeatureFlagCreate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    flag = await service.create_feature_flag(db, body.model_dump(), admin.id)
    return {"data": schemas.FeatureFlagResponse.model_validate(flag)}


@router.put("/feature-flags/{key}")
async def update_feature_flag(
    key: str,
    body: schemas.FeatureFlagUpdate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    flag = await service.update_feature_flag(db, key, body.model_dump(exclude_unset=True), admin.id)
    if not flag:
        raise HTTPException(404, "Feature flag not found")
    return {"data": schemas.FeatureFlagResponse.model_validate(flag)}


@router.delete("/feature-flags/{key}")
async def delete_feature_flag(
    key: str,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await service.delete_feature_flag(db, key)
    if not deleted:
        raise HTTPException(404, "Feature flag not found")
    return {"data": {"deleted": True}}


# ── Public pricing (any authenticated user) ───────────────────────────────

@router.get("/pricing")
async def get_public_pricing(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return pricing settings visible to any authenticated user."""
    settings_list = await service.list_platform_settings(db, "pricing")
    return {"data": {s.key: s.value for s in settings_list}}


# ── Platform settings (pricing, limits, etc.) ────────────────────────────

@router.get("/settings")
async def list_platform_settings(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = Query(None),
):
    settings_list = await service.list_platform_settings(db, category)
    return {"data": [schemas.PlatformSettingResponse.model_validate(s) for s in settings_list]}


@router.post("/settings", status_code=201)
async def create_platform_setting(
    body: schemas.PlatformSettingCreate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    setting = await service.create_platform_setting(db, body.model_dump(), admin.id)
    return {"data": schemas.PlatformSettingResponse.model_validate(setting)}


@router.put("/settings/{key}")
async def update_platform_setting(
    key: str,
    body: schemas.PlatformSettingUpdate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    setting = await service.update_platform_setting(
        db, key, body.model_dump(exclude_unset=True), admin.id
    )
    if not setting:
        raise HTTPException(404, "Setting not found")
    return {"data": schemas.PlatformSettingResponse.model_validate(setting)}


# ── Health ───────────────────────────────────────────────────────────────

@router.get("/health")
async def system_health(
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    health = await service.get_system_health(db, request.app.state.settings)
    return {"data": health}


# ── Error logs ───────────────────────────────────────────────────────────

@router.get("/errors")
async def list_errors(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    level: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    errors, total = await service.list_error_logs(db, level, resolved, page, page_size)
    return {
        "data": [schemas.ErrorLogResponse.model_validate(e) for e in errors],
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.post("/errors/{error_id}/resolve")
async def resolve_error(
    error_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    resolved = await service.resolve_error(db, error_id, admin.id)
    if not resolved:
        raise HTTPException(404, "Error not found")
    return {"data": {"resolved": True}}


# ── Users (enhanced management) ──────────────────────────────────────────

@router.get("/users")
async def list_users(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    users, total = await service.get_users_list(db, search, role, is_active, page, page_size)
    return {
        "data": users,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    detail = await service.get_user_detail(db, user_id)
    if not detail:
        raise HTTPException(404, "User not found")
    return {"data": detail}


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = await service.generate_impersonation_token(db, user_id, admin)
    if not token:
        raise HTTPException(404, "User not found or inactive")
    return {"data": {"access_token": token, "token_type": "bearer", "expires_in": 900}}


# ── Activity log ─────────────────────────────────────────────────────────

@router.get("/activity")
async def get_activity_log(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    logs, total = await service.get_activity_log(db, user_id, action, resource_type, page, page_size)
    return {
        "data": logs,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── Security: Sessions ──────────────────────────────────────────────────

@router.get("/sessions")
async def list_active_sessions(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sessions = await service.get_active_sessions(db)
    return {"data": sessions}


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    revoked = await service.revoke_session(db, session_id)
    if not revoked:
        raise HTTPException(404, "Session not found")
    return {"data": {"revoked": True}}


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_user_sessions(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    count = await service.revoke_all_user_sessions(db, user_id)
    return {"data": {"revoked_count": count}}


# ── API key status ───────────────────────────────────────────────────────

@router.get("/api-keys")
async def list_api_key_status(
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
):
    """Show which API keys are configured (masked) and which are missing."""
    s = request.app.state.settings

    def mask(val: str) -> str | None:
        if not val:
            return None
        if len(val) <= 8:
            return "****" + val[-2:]
        return "****" + val[-4:]

    keys = [
        {
            "integration": "anthropic",
            "configured": bool(s.anthropic_api_key),
            "masked_key": mask(s.anthropic_api_key),
            "fields": [{"name": "anthropic_api_key", "configured": bool(s.anthropic_api_key)}],
        },
        {
            "integration": "gemini",
            "configured": bool(s.gemini_api_key),
            "masked_key": mask(s.gemini_api_key),
            "fields": [{"name": "gemini_api_key", "configured": bool(s.gemini_api_key)}],
        },
        {
            "integration": "openai",
            "configured": bool(s.openai_api_key),
            "masked_key": mask(s.openai_api_key),
            "fields": [{"name": "openai_api_key", "configured": bool(s.openai_api_key)}],
        },
        {
            "integration": "stripe",
            "configured": bool(s.stripe_secret_key),
            "masked_key": mask(s.stripe_secret_key),
            "fields": [
                {"name": "stripe_secret_key", "configured": bool(s.stripe_secret_key)},
                {"name": "stripe_publishable_key", "configured": bool(s.stripe_publishable_key)},
                {"name": "stripe_webhook_secret", "configured": bool(s.stripe_webhook_secret)},
            ],
        },
        {
            "integration": "twilio",
            "configured": bool(s.twilio_account_sid and s.twilio_auth_token),
            "masked_key": mask(s.twilio_account_sid),
            "fields": [
                {"name": "twilio_account_sid", "configured": bool(s.twilio_account_sid)},
                {"name": "twilio_auth_token", "configured": bool(s.twilio_auth_token)},
                {"name": "twilio_from_number", "configured": bool(s.twilio_from_number)},
            ],
        },
        {
            "integration": "plaid",
            "configured": bool(s.plaid_client_id and s.plaid_secret),
            "masked_key": mask(s.plaid_client_id),
            "fields": [
                {"name": "plaid_client_id", "configured": bool(s.plaid_client_id)},
                {"name": "plaid_secret", "configured": bool(s.plaid_secret)},
            ],
        },
        {
            "integration": "google",
            "configured": bool(s.google_client_id and s.google_client_secret),
            "masked_key": mask(s.google_client_id),
            "fields": [
                {"name": "google_client_id", "configured": bool(s.google_client_id)},
                {"name": "google_client_secret", "configured": bool(s.google_client_secret)},
            ],
        },
        {
            "integration": "livekit",
            "configured": bool(s.livekit_api_key and s.livekit_api_secret),
            "masked_key": mask(s.livekit_api_key),
            "fields": [
                {"name": "livekit_api_key", "configured": bool(s.livekit_api_key)},
                {"name": "livekit_api_secret", "configured": bool(s.livekit_api_secret)},
                {"name": "livekit_url", "configured": bool(s.livekit_url)},
            ],
        },
        {
            "integration": "smtp",
            "configured": bool(s.smtp_host and s.smtp_username),
            "masked_key": mask(s.smtp_username),
            "fields": [
                {"name": "smtp_host", "configured": bool(s.smtp_host)},
                {"name": "smtp_username", "configured": bool(s.smtp_username)},
                {"name": "smtp_password", "configured": bool(s.smtp_password)},
            ],
        },
        {
            "integration": "cloudflare_r2",
            "configured": bool(s.r2_access_key_id),
            "masked_key": mask(s.r2_access_key_id),
            "fields": [
                {"name": "r2_access_key_id", "configured": bool(s.r2_access_key_id)},
                {"name": "r2_secret_access_key", "configured": bool(s.r2_secret_access_key)},
                {"name": "r2_bucket_name", "configured": bool(s.r2_bucket_name)},
            ],
        },
    ]
    return {"data": keys}
