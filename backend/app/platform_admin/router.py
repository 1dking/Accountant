"""API endpoints for platform administration."""

import json
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
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
    endpoint: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    errors, total = await service.list_error_logs(
        db, level, resolved, page, page_size,
        endpoint=endpoint, date_from=date_from, date_to=date_to,
    )
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


# ── User CRUD ─────────────────────────────────────────────────────────────


class PlatformCreateUser(BaseModel):
    email: str
    full_name: str
    role: str = "viewer"
    password: str | None = None
    send_invite: bool = False
    feature_access: dict[str, bool] | None = None


class PlatformUpdateUser(BaseModel):
    email: str | None = None
    full_name: str | None = None
    role: str | None = None
    password: str | None = None
    feature_access: dict[str, bool] | None = None
    is_active: bool | None = None


@router.post("/users")
async def platform_create_user(
    body: PlatformCreateUser,
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a user from Platform Admin. Optionally send invite email."""
    import json
    from app.auth.models import Role as AuthRole
    from app.auth.service import create_user, generate_invite_token, user_to_response_dict
    from app.auth.utils import hash_password

    role_map = {r.value: r for r in AuthRole}
    role = role_map.get(body.role, AuthRole.VIEWER)

    user = await create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=role,
        feature_access=body.feature_access,
    )

    invite_link = None
    if body.send_invite:
        settings = request.app.state.settings
        token = generate_invite_token(user.id, settings)
        base_url = getattr(settings, "frontend_url", "") or f"https://{request.headers.get('host', 'localhost')}"
        invite_link = f"{base_url}/invite?token={token}"

        # Try to send invite email
        if settings.smtp_host and settings.smtp_username:
            try:
                from app.email.service import send_email, render_template, resolve_smtp_config
                smtp_config = await resolve_smtp_config(db, admin)
                if smtp_config:
                    html = render_template("invite.html", full_name=body.full_name, invite_link=invite_link)
                    await send_email(smtp_config, body.email, "You're invited to O-Brain", html)
            except Exception:
                pass  # Fallback: admin copies the link

    resp = user_to_response_dict(user)
    if invite_link:
        resp["invite_link"] = invite_link
    return {"data": resp}


@router.put("/users/{user_id}")
async def platform_update_user(
    user_id: uuid.UUID,
    body: PlatformUpdateUser,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a user from Platform Admin."""
    from app.auth.schemas import AdminUserUpdate as AuthUpdate
    from app.auth.service import admin_update_user as auth_update, user_to_response_dict
    from app.auth.models import Role as AuthRole

    role_map = {r.value: r for r in AuthRole}
    update = AuthUpdate(
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role=role_map.get(body.role) if body.role else None,
        feature_access=body.feature_access,
        is_active=body.is_active,
    )
    user = await auth_update(db, str(user_id), update)
    return {"data": user_to_response_dict(user)}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.auth.service import deactivate_user as deactivate_svc
    email = await deactivate_svc(db, str(user_id))
    return {"data": {"message": f"User {email} deactivated"}}


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = True
    await db.commit()
    return {"data": {"message": f"User {user.email} reactivated"}}


@router.get("/features/defaults")
async def get_feature_defaults(
    admin: Annotated[User, Depends(require_platform_admin)],
):
    """Return feature categories and role defaults for the frontend."""
    from app.auth.features import FEATURE_CATEGORIES, ROLE_DEFAULTS
    return {"data": {"categories": FEATURE_CATEGORIES, "role_defaults": ROLE_DEFAULTS}}


# ── API key management ────────────────────────────────────────────────────


class ApiKeysSaveRequest(BaseModel):
    config: dict[str, str]


def _mask(val: str) -> str:
    if not val:
        return ""
    if len(val) <= 8:
        return "****" + val[-2:]
    return "****" + val[-4:]


@router.get("/api-keys")
async def list_api_key_status(
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
):
    """Show all integrations with per-field masked values."""
    from app.integrations.settings_router import INTEGRATION_FIELDS, SETTINGS_MAP, NON_SECRET_FIELDS
    s = request.app.state.settings

    result = []
    for integration, fields in INTEGRATION_FIELDS.items():
        mapping = SETTINGS_MAP.get(integration, {})
        non_secret = NON_SECRET_FIELDS.get(integration, set())

        field_list = []
        any_configured = False
        for field in fields:
            setting_attr = mapping.get(field, "")
            val = str(getattr(s, setting_attr, "")) if setting_attr else ""
            is_configured = bool(val)
            if is_configured:
                any_configured = True
            # Non-secret fields: show full value; secret fields: mask
            masked = val if (field in non_secret and val) else (_mask(val) if val else "")
            field_list.append({"name": field, "configured": is_configured, "masked_value": masked})

        result.append({
            "integration": integration,
            "configured": any_configured,
            "fields": field_list,
        })

    return {"data": result}


@router.put("/api-keys/{integration}")
async def save_api_keys(
    integration: str,
    body: ApiKeysSaveRequest,
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Save or update API keys for an integration (encrypted in DB)."""
    from app.integrations.settings_router import INTEGRATION_FIELDS, SETTINGS_MAP
    from app.integrations.settings_models import IntegrationConfig
    from app.core.encryption import get_encryption_service

    if integration not in INTEGRATION_FIELDS:
        raise HTTPException(400, f"Unknown integration: {integration}")

    allowed = set(INTEGRATION_FIELDS[integration])
    for key in body.config:
        if key not in allowed:
            raise HTTPException(400, f"Unknown field: {key}")

    enc = get_encryption_service()

    # Load existing to merge
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.integration_type == integration)
    )
    existing = result.scalar_one_or_none()
    existing_config: dict = {}
    if existing:
        existing_config = json.loads(enc.decrypt(existing.encrypted_config))

    # Merge: skip masked placeholders
    new_config = dict(existing_config)
    for key, val in body.config.items():
        if val and not val.startswith("****"):
            new_config[key] = val
        elif val == "":
            new_config.pop(key, None)

    encrypted = enc.encrypt(json.dumps(new_config))

    if existing:
        existing.encrypted_config = encrypted
        existing.updated_by = admin.id
    else:
        db.add(IntegrationConfig(
            integration_type=integration,
            encrypted_config=encrypted,
            updated_by=admin.id,
        ))

    await db.commit()

    # Update runtime settings immediately
    mapping = SETTINGS_MAP.get(integration, {})
    settings = request.app.state.settings
    for field, setting_attr in mapping.items():
        val = new_config.get(field, "")
        if val:
            setattr(settings, setting_attr, val)
        else:
            setattr(settings, setting_attr, "")

    return {"data": {"message": f"{integration} keys saved"}}


@router.delete("/api-keys/{integration}")
async def remove_api_keys(
    integration: str,
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove all stored keys for an integration."""
    from app.integrations.settings_router import INTEGRATION_FIELDS, SETTINGS_MAP
    from app.integrations.settings_models import IntegrationConfig
    from sqlalchemy import delete as sa_delete

    if integration not in INTEGRATION_FIELDS:
        raise HTTPException(400, f"Unknown integration: {integration}")

    await db.execute(
        sa_delete(IntegrationConfig).where(IntegrationConfig.integration_type == integration)
    )
    await db.commit()

    # Clear runtime settings
    mapping = SETTINGS_MAP.get(integration, {})
    settings = request.app.state.settings
    for _field, setting_attr in mapping.items():
        setattr(settings, setting_attr, "")

    return {"data": {"message": f"{integration} keys removed"}}


@router.post("/api-keys/{integration}/test")
async def test_api_connection(
    integration: str,
    request: Request,
    admin: Annotated[User, Depends(require_platform_admin)],
):
    """Test connectivity for an integration. Returns status and latency."""
    import time
    import httpx

    s = request.app.state.settings
    start = time.monotonic()
    detail = ""

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if integration == "anthropic":
                if not s.anthropic_api_key:
                    return {"data": {"status": "unconfigured", "message": "No API key set"}}
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01"},
                )
                r.raise_for_status()
                detail = f"{len(r.json().get('data', []))} models available"

            elif integration == "gemini":
                if not s.gemini_api_key:
                    return {"data": {"status": "unconfigured", "message": "No API key set"}}
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={s.gemini_api_key}"
                )
                r.raise_for_status()
                detail = f"{len(r.json().get('models', []))} models available"

            elif integration == "openai":
                if not s.openai_api_key:
                    return {"data": {"status": "unconfigured", "message": "No API key set"}}
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {s.openai_api_key}"},
                )
                r.raise_for_status()
                detail = f"{len(r.json().get('data', []))} models available"

            elif integration == "stripe":
                if not s.stripe_secret_key:
                    return {"data": {"status": "unconfigured", "message": "No secret key set"}}
                r = await client.get(
                    "https://api.stripe.com/v1/balance",
                    auth=(s.stripe_secret_key, ""),
                )
                r.raise_for_status()
                detail = "Balance retrieved"

            elif integration == "twilio":
                if not s.twilio_account_sid or not s.twilio_auth_token:
                    return {"data": {"status": "unconfigured", "message": "Account SID or auth token missing"}}
                r = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}.json",
                    auth=(s.twilio_account_sid, s.twilio_auth_token),
                )
                r.raise_for_status()
                detail = f"Account: {r.json().get('friendly_name', 'OK')}"

            elif integration == "plaid":
                if not s.plaid_client_id or not s.plaid_secret:
                    return {"data": {"status": "unconfigured", "message": "Client ID or secret missing"}}
                env_url = {"sandbox": "sandbox", "development": "development", "production": "production"}.get(s.plaid_env, "sandbox")
                r = await client.post(
                    f"https://{env_url}.plaid.com/categories/get",
                    json={},
                    headers={"Content-Type": "application/json"},
                )
                r.raise_for_status()
                detail = "Categories endpoint reachable"

            elif integration == "google":
                if not s.google_client_id:
                    return {"data": {"status": "unconfigured", "message": "No client ID set"}}
                detail = "OAuth client configured (cannot test without user flow)"
                elapsed = int((time.monotonic() - start) * 1000)
                return {"data": {"status": "configured", "message": detail, "latency_ms": elapsed}}

            elif integration == "livekit":
                if not s.livekit_url:
                    return {"data": {"status": "unconfigured", "message": "No LiveKit URL set"}}
                url = s.livekit_url.rstrip("/")
                if not url.startswith("http"):
                    url = "https://" + url
                r = await client.get(url, follow_redirects=True)
                detail = f"Server reachable (HTTP {r.status_code})"

            elif integration == "smtp":
                if not s.smtp_host:
                    return {"data": {"status": "unconfigured", "message": "No SMTP host set"}}
                import smtplib
                smtp = smtplib.SMTP(s.smtp_host, int(s.smtp_port) if s.smtp_port else 587, timeout=10)
                smtp.ehlo()
                if s.smtp_use_tls:
                    smtp.starttls()
                if s.smtp_username and s.smtp_password:
                    smtp.login(s.smtp_username, s.smtp_password)
                smtp.quit()
                detail = "SMTP connection successful"

            elif integration == "cloudflare_r2":
                if not s.r2_access_key_id:
                    return {"data": {"status": "unconfigured", "message": "No R2 credentials set"}}
                import boto3
                s3 = boto3.client(
                    "s3",
                    endpoint_url=s.r2_endpoint or f"https://{s.cloudflare_account_id}.r2.cloudflarestorage.com",
                    aws_access_key_id=s.r2_access_key_id,
                    aws_secret_access_key=s.r2_secret_access_key,
                    region_name="auto",
                )
                s3.head_bucket(Bucket=s.r2_bucket_name)
                detail = f"Bucket '{s.r2_bucket_name}' accessible"

            elif integration == "assemblyai":
                if not s.assemblyai_api_key:
                    return {"data": {"status": "unconfigured", "message": "No API key set"}}
                r = await client.get(
                    "https://api.assemblyai.com/v2/transcript",
                    headers={"Authorization": s.assemblyai_api_key},
                    params={"limit": 1},
                )
                r.raise_for_status()
                detail = "API reachable"

            else:
                return {"data": {"status": "error", "message": f"No test available for {integration}"}}

        elapsed = int((time.monotonic() - start) * 1000)
        return {"data": {"status": "healthy", "message": detail, "latency_ms": elapsed}}

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return {"data": {"status": "error", "message": str(e)[:300], "latency_ms": elapsed}}


# ── Organizations ───────────────────────────────────────────────────


@router.get("/organizations")
async def list_organizations(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    orgs, total = await service.list_organizations(db, search, plan, is_active, page, page_size)
    return {
        "data": orgs,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.post("/organizations", status_code=201)
async def create_organization(
    body: schemas.OrganizationCreate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    org = await service.create_organization(db, body.model_dump())
    detail = await service.get_organization(db, org.id)
    return {"data": detail}


@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    detail = await service.get_organization(db, org_id)
    if not detail:
        raise HTTPException(404, "Organization not found")
    return {"data": detail}


@router.put("/organizations/{org_id}")
async def update_organization(
    org_id: uuid.UUID,
    body: schemas.OrganizationUpdate,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    org = await service.update_organization(db, org_id, body.model_dump(exclude_unset=True))
    if not org:
        raise HTTPException(404, "Organization not found")
    detail = await service.get_organization(db, org.id)
    return {"data": detail}


@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await service.delete_organization(db, org_id)
    if not deleted:
        raise HTTPException(404, "Organization not found")
    return {"data": {"deleted": True}}


# ── Org feature overrides ──────────────────────────────────────────


@router.put("/organizations/{org_id}/features/{feature_key}")
async def set_org_feature_override(
    org_id: uuid.UUID,
    feature_key: str,
    body: schemas.OrgFeatureOverrideSet,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    override = await service.set_org_feature_override(db, org_id, feature_key, body.enabled)
    return {"data": {"feature_key": override.feature_key, "enabled": override.enabled}}


@router.delete("/organizations/{org_id}/features/{feature_key}")
async def delete_org_feature_override(
    org_id: uuid.UUID,
    feature_key: str,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await service.delete_org_feature_override(db, org_id, feature_key)
    if not deleted:
        raise HTTPException(404, "Override not found")
    return {"data": {"deleted": True}}


# ── Org setting overrides ──────────────────────────────────────────


@router.put("/organizations/{org_id}/settings/{setting_key}")
async def set_org_setting_override(
    org_id: uuid.UUID,
    setting_key: str,
    body: schemas.OrgSettingOverrideSet,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    override = await service.set_org_setting_override(db, org_id, setting_key, body.value)
    return {"data": {"setting_key": override.setting_key, "value": override.value}}


@router.delete("/organizations/{org_id}/settings/{setting_key}")
async def delete_org_setting_override(
    org_id: uuid.UUID,
    setting_key: str,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await service.delete_org_setting_override(db, org_id, setting_key)
    if not deleted:
        raise HTTPException(404, "Override not found")
    return {"data": {"deleted": True}}


# ── Org members ─────────────────────────────────────────────────────


@router.post("/organizations/{org_id}/members")
async def add_org_member(
    org_id: uuid.UUID,
    body: schemas.OrgAddMemberRequest,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    added = await service.add_org_member(db, org_id, body.user_id)
    if not added:
        raise HTTPException(404, "User not found")
    return {"data": {"added": True}}


@router.delete("/organizations/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    removed = await service.remove_org_member(db, org_id, user_id)
    if not removed:
        raise HTTPException(404, "Member not found in organization")
    return {"data": {"removed": True}}
