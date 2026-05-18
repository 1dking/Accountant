
import logging
import secrets
import time
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    GoogleAuthRequest,
    InviteCompleteRequest,
    TokenRefreshRequest,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
    VoicemailGreetingPreview,
)
from app.auth.service import admin_update_user as admin_update_user_svc
from app.auth.service import (
    authenticate_google,
    authenticate_user,
    complete_invite,
    create_user,
    refresh_tokens,
    register_user,
    revoke_refresh_token,
    update_user_profile,
    user_to_response_dict,
    validate_invite_token,
)
from app.auth.service import deactivate_user as deactivate_user_svc
from app.auth.service import list_users as list_users_svc
from app.auth.service import update_user_role as update_user_role_svc
from app.core.exceptions import RateLimitError, ValidationError
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
# OAuth CSRF state tokens: state -> expiry timestamp
_oauth_states: dict[str, float] = {}
_OAUTH_STATE_TTL = 600  # 10 minutes

# Maps IP address -> (attempt_count, window_start_timestamp)
_login_attempts: dict[str, tuple[int, float]] = {}
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 60
_login_request_counter = 0
_CLEANUP_EVERY = 100


def _check_login_rate_limit(client_ip: str) -> None:
    """Raise RateLimitError if the IP has exceeded the login attempt limit.

    Also performs periodic cleanup of expired entries to prevent unbounded
    memory growth.
    """
    global _login_request_counter  # noqa: PLW0603

    now = time.monotonic()

    # Periodic cleanup: purge entries whose window has expired
    _login_request_counter += 1
    if _login_request_counter >= _CLEANUP_EVERY:
        _login_request_counter = 0
        expired_ips = [
            ip
            for ip, (_, window_start) in _login_attempts.items()
            if now - window_start >= _LOGIN_WINDOW_SECONDS
        ]
        for ip in expired_ips:
            del _login_attempts[ip]

    # Look up current state for this IP
    entry = _login_attempts.get(client_ip)

    if entry is None:
        # First attempt in this window
        _login_attempts[client_ip] = (1, now)
        return

    count, window_start = entry

    if now - window_start >= _LOGIN_WINDOW_SECONDS:
        # Window expired -- reset
        _login_attempts[client_ip] = (1, now)
        return

    if count >= _LOGIN_MAX_ATTEMPTS:
        retry_after = int(_LOGIN_WINDOW_SECONDS - (now - window_start)) + 1
        raise RateLimitError(
            f"Too many login attempts. Please try again in {retry_after} seconds."
        )

    # Increment count within the current window
    _login_attempts[client_ip] = (count + 1, window_start)


@router.post("/register", status_code=201)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    user = await register_user(db, user_data, request.app.state.settings)
    return {"data": UserResponse.model_validate(user)}


@router.post("/login")
async def login(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    _check_login_rate_limit(request.client.host if request.client else "unknown")
    tokens = await authenticate_user(db, credentials.email, credentials.password, request.app.state.settings)
    return {"data": tokens}


@router.post("/refresh")
async def refresh(
    body: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    tokens = await refresh_tokens(db, body.refresh_token, request.app.state.settings)
    return {"data": tokens}


@router.post("/logout")
async def logout(
    body: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    await revoke_refresh_token(db, body.refresh_token)
    return {"data": {"message": "Logged out successfully"}}


@router.get("/me")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": user_to_response_dict(current_user)}


@router.put("/me")
async def update_me(
    updates: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await update_user_profile(db, current_user, updates)
    return {"data": UserResponse.model_validate(user)}


@router.post("/me/conversation-preview")
async def preview_conversation_reply(
    body: dict,
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Generate a sample AI reply using the user's draft template +
    tone — WITHOUT saving anything or sending an SMS. Lets users eyeball
    output before clicking Save in Settings → Automation."""
    from app.communication.conversation_engine import generate_preview

    template = (body.get("template") or "").strip()
    instructions = body.get("ai_instructions") or None
    sample = body.get("sample_inbound") or None
    if not template:
        raise HTTPException(
            status_code=400,
            detail="template is required (the voice you want AI to mirror)",
        )
    try:
        result = await generate_preview(template, instructions, sample)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI preview failed: {str(e)[:160]}",
        )
    return {"data": result}


@router.get("/me/onboarding")
async def get_my_onboarding(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return the live onboarding checklist for the current user."""
    from app.auth.onboarding import compute_items, compute_progress

    items = await compute_items(db, current_user)
    return {
        "data": {
            "items": items,
            "overall_progress": compute_progress(items),
        }
    }


@router.post("/me/onboarding/{item_key}/dismiss")
async def dismiss_my_onboarding_item(
    item_key: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Mark an onboarding item as dismissed."""
    from app.auth.onboarding import compute_items, dismiss_item

    # Validate the item_key against the live checklist
    items = await compute_items(db, current_user)
    known_keys = {i["key"] for i in items}
    if item_key not in known_keys:
        raise HTTPException(status_code=400, detail="Unknown onboarding item")
    # Some items aren't dismissible (e.g., phone_configured is required)
    target = next((i for i in items if i["key"] == item_key), None)
    if target and not target.get("can_dismiss", True):
        raise HTTPException(
            status_code=400, detail="This item cannot be dismissed"
        )

    new_state = await dismiss_item(db, current_user, item_key)
    return {"data": {"onboarding_state": new_state}}


@router.get("/me/voicemail-greeting")
async def get_my_voicemail_greeting(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return the current user's voicemail-greeting config for in-place editing.

    Shape:
        { type: 'text', text: '<full text>' }              if text
        { type: 'audio', storage_key: '<key>' }           if audio
        { type: None }                                     if no custom
    """
    if current_user.voicemail_greeting_type == "text":
        payload = VoicemailGreetingPreview(
            type="text", text=current_user.voicemail_greeting_text
        )
    elif current_user.voicemail_greeting_type == "audio":
        payload = VoicemailGreetingPreview(
            type="audio", storage_key=current_user.voicemail_greeting_storage_key
        )
    else:
        payload = VoicemailGreetingPreview(type=None)
    return {"data": payload}


@router.post("/me/voicemail-greeting")
async def upload_my_voicemail_greeting(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    greeting_type: Annotated[str, Form()],
    text: Annotated[str | None, Form()] = None,
    audio_file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """Save voicemail greeting. Text path is direct DB write; audio path
    transcodes to mp3 via ffmpeg + uploads to R2 + replaces any prior audio."""
    from app.communication.voicemail_storage import (
        ALLOWED_AUDIO_MIME_TYPES,
        MAX_GREETING_SIZE_BYTES,
        delete_greeting,
        save_greeting,
        transcode_to_mp3,
    )
    settings = request.app.state.settings

    if greeting_type == "text":
        if not text or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="text is required"
            )
        if len(text) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text exceeds 500 chars",
            )
        old_key = current_user.voicemail_greeting_storage_key
        current_user.voicemail_greeting_type = "text"
        current_user.voicemail_greeting_text = text.strip()
        current_user.voicemail_greeting_storage_key = None
        await db.commit()
        if old_key:
            await delete_greeting(settings, old_key)
        return {"data": {"type": "text", "text": text.strip()}}

    if greeting_type == "audio":
        if audio_file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="audio_file is required",
            )
        # Strip codec parameters before whitelist check. MediaRecorder
        # blobs come through as e.g. 'audio/webm;codecs=opus' — the bare
        # 'audio/webm' is in our set but the full string isn't, so an
        # exact-membership check rejects valid recordings.
        base_mime = (audio_file.content_type or "").split(";")[0].strip().lower()
        if base_mime not in ALLOWED_AUDIO_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported content type: {audio_file.content_type}",
            )
        raw = await audio_file.read()
        if len(raw) > MAX_GREETING_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio exceeds 5MB limit",
            )
        try:
            mp3_bytes = await transcode_to_mp3(raw, base_mime)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio rejected: {str(e)[:120]}",
            )
        new_key = await save_greeting(settings, current_user.id, mp3_bytes)
        old_key = current_user.voicemail_greeting_storage_key
        current_user.voicemail_greeting_type = "audio"
        current_user.voicemail_greeting_storage_key = new_key
        current_user.voicemail_greeting_text = None
        await db.commit()
        if old_key and old_key != new_key:
            await delete_greeting(settings, old_key)
        return {"data": {"type": "audio", "storage_key": new_key}}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="greeting_type must be 'audio' or 'text'",
    )


@router.delete("/me/voicemail-greeting")
async def delete_my_voicemail_greeting(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Revert to default Polly.Joanna greeting. Cleans up R2 if audio existed."""
    from app.communication.voicemail_storage import delete_greeting
    settings = request.app.state.settings
    old_key = current_user.voicemail_greeting_storage_key
    current_user.voicemail_greeting_type = None
    current_user.voicemail_greeting_text = None
    current_user.voicemail_greeting_storage_key = None
    await db.commit()
    if old_key:
        await delete_greeting(settings, old_key)
    return {"data": {"type": None}}


@router.get("/users")
async def list_users(
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    users, meta = await list_users_svc(db, pagination)
    return {"data": [UserResponse.model_validate(u) for u in users], "meta": meta}


@router.post("/users", status_code=201)
async def admin_create_user(
    body: AdminUserCreate,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await create_user(db, body.email, body.password, body.full_name, body.role, body.feature_access)
    return {"data": user_to_response_dict(user)}


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await admin_update_user_svc(db, user_id, body)
    return {"data": user_to_response_dict(user)}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await update_user_role_svc(db, user_id, body.role)
    return {"data": UserResponse.model_validate(user)}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    email = await deactivate_user_svc(db, user_id)
    return {"data": {"message": f"User {email} deactivated"}}


# ---------------------------------------------------------------------------
# Invite flow
# ---------------------------------------------------------------------------


@router.get("/invite/validate/{token}")
async def validate_invite(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    user = await validate_invite_token(db, token, request.app.state.settings)
    return {"data": {"valid": True, "email": user.email, "full_name": user.full_name}}


@router.post("/invite/complete")
async def complete_invite_endpoint(
    body: InviteCompleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    tokens = await complete_invite(db, body.token, body.password, request.app.state.settings)
    return {"data": tokens}


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect the browser to Google's consent screen."""
    settings = request.app.state.settings
    if not settings.google_client_id:
        raise ValidationError("Google OAuth is not configured.")

    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.monotonic() + _OAUTH_STATE_TTL
    # Cleanup expired states
    now = time.monotonic()
    expired = [s for s, exp in _oauth_states.items() if exp < now]
    for s in expired:
        _oauth_states.pop(s, None)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.post("/google/callback")
async def google_callback(
    body: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    """Exchange Google auth code for tokens, then find/create user."""
    import httpx

    settings = request.app.state.settings
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValidationError("Google OAuth is not configured.")

    # Validate CSRF state token
    if body.state:
        expiry = _oauth_states.pop(body.state, None)
        if expiry is None or time.monotonic() > expiry:
            raise ValidationError("Invalid or expired OAuth state. Please try again.")

    # Whitelist allowed redirect URIs
    allowed_uris = [
        settings.google_oauth_redirect_uri,
        "http://localhost:5173/auth/google/callback",
    ]
    redirect_uri = body.redirect_uri or settings.google_oauth_redirect_uri
    if redirect_uri not in allowed_uris:
        raise ValidationError("Invalid redirect URI.")

    # Exchange auth code for Google tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": body.code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        logger.error("Google token exchange failed: %s", token_resp.text)
        raise ValidationError("Failed to authenticate with Google.")

    google_tokens = token_resp.json()
    access_token = google_tokens.get("access_token")
    if not access_token:
        raise ValidationError("No access token from Google.")

    # Get user info from Google
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise ValidationError("Failed to get user info from Google.")

    userinfo = userinfo_resp.json()
    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    full_name = userinfo.get("name", "")

    if not google_id or not email:
        raise ValidationError("Incomplete user info from Google.")

    tokens = await authenticate_google(db, google_id, email, full_name, settings)
    return {"data": tokens}
