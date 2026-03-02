
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    TokenRefreshRequest,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
)
from app.auth.service import admin_update_user as admin_update_user_svc
from app.auth.service import (
    authenticate_user,
    create_user,
    refresh_tokens,
    register_user,
    revoke_refresh_token,
    update_user_profile,
)
from app.auth.service import deactivate_user as deactivate_user_svc
from app.auth.service import list_users as list_users_svc
from app.auth.service import update_user_role as update_user_role_svc
from app.core.exceptions import RateLimitError
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory rate limiter for login endpoint
# ---------------------------------------------------------------------------
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
    return {"data": UserResponse.model_validate(current_user)}


@router.put("/me")
async def update_me(
    updates: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await update_user_profile(db, current_user, updates)
    return {"data": UserResponse.model_validate(user)}


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
    user = await create_user(db, body.email, body.password, body.full_name, body.role)
    return {"data": UserResponse.model_validate(user)}


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await admin_update_user_svc(db, user_id, body)
    return {"data": UserResponse.model_validate(user)}


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
