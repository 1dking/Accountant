
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.auth.features import resolve_feature_access
from app.auth.models import RefreshToken, Role, User
from app.auth.schemas import AdminUserUpdate, TokenResponse, UserCreate, UserUpdate
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.collaboration.service import log_activity
from app.config import Settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta


async def register_user(
    db: AsyncSession,
    user_data: UserCreate,
    settings: Settings,
) -> User:
    # Only allow registration when no users exist (first-time setup)
    user_count = await db.scalar(select(func.count()).select_from(User))
    if user_count > 0:
        raise ForbiddenError("Registration is closed. Contact an admin to get an account.")

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A user with email {user_data.email} already exists.")

    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=Role.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_activity(
        db,
        user_id=user.id,
        action="user_registered",
        resource_type="user",
        resource_id=str(user.id),
        details={"email": user.email, "role": user.role.value},
    )

    return user


async def create_user(
    db: AsyncSession,
    email: str,
    password: str | None,
    full_name: str,
    role: Role,
    feature_access: dict[str, bool] | None = None,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A user with email {email} already exists.")

    user = User(
        email=email,
        hashed_password=hash_password(password) if password else None,
        full_name=full_name,
        role=role,
        feature_access_json=json.dumps(feature_access) if feature_access else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise ValidationError("Invalid email or password.")

    if not user.is_active:
        raise ValidationError("Account is deactivated.")

    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)

    # Store refresh token hash
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token_record)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="user_login",
        resource_type="user",
        resource_id=str(user.id),
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(
    db: AsyncSession,
    refresh_token: str,
    settings: Settings,
) -> TokenResponse:
    from app.auth.utils import decode_token

    token_data = decode_token(refresh_token, settings)
    if token_data is None:
        raise ValidationError("Invalid or expired refresh token.")

    # Find and validate stored token
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        raise ValidationError("Refresh token not found or already revoked.")

    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise ValidationError("Refresh token has expired.")

    # Revoke old token
    stored_token.revoked = True

    # Get user for new tokens
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ValidationError("User not found or inactive.")

    # Create new token pair
    new_access = create_access_token(user.id, user.role.value, settings)
    new_refresh = create_refresh_token(user.id, settings)

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_token_record)
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored_token = result.scalar_one_or_none()
    if stored_token:
        stored_token.revoked = True
        await db.commit()


async def update_user_profile(
    db: AsyncSession,
    user: User,
    updates: UserUpdate,
) -> User:
    if updates.full_name is not None:
        user.full_name = updates.full_name
    if updates.password is not None:
        user.hashed_password = hash_password(updates.password)
    await db.commit()
    await db.refresh(user)

    await log_activity(
        db,
        user_id=user.id,
        action="profile_updated",
        resource_type="user",
        resource_id=str(user.id),
    )

    return user


async def list_users(
    db: AsyncSession,
    pagination: PaginationParams | None = None,
) -> list[User] | tuple[list[User], dict]:
    query = select(User).order_by(User.created_at)

    if pagination is None:
        result = await db.execute(query)
        return list(result.scalars().all())

    total = await db.scalar(select(func.count()).select_from(User)) or 0
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())
    return users, build_pagination_meta(total, pagination)


async def admin_update_user(
    db: AsyncSession,
    user_id: str,
    updates: AdminUserUpdate,
) -> User:
    result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    if updates.email is not None and updates.email != user.email:
        existing = await db.execute(select(User).where(User.email == updates.email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"A user with email {updates.email} already exists.")
        user.email = updates.email
    if updates.full_name is not None:
        user.full_name = updates.full_name
    if updates.password is not None:
        user.hashed_password = hash_password(updates.password)
    if updates.role is not None:
        user.role = updates.role
    if updates.feature_access is not None:
        user.feature_access_json = json.dumps(updates.feature_access)
    if updates.is_active is not None:
        user.is_active = updates.is_active
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_role(
    db: AsyncSession,
    user_id: str,
    role: Role,
) -> User:
    result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate_user(
    db: AsyncSession,
    user_id: str,
) -> str:
    result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    user.is_active = False
    await db.commit()
    return user.email


async def authenticate_google(
    db: AsyncSession,
    google_id: str,
    email: str,
    full_name: str,
    settings: Settings,
) -> TokenResponse:
    """Find or create a user from Google OAuth, then issue JWT tokens."""
    # First try to find by google_id
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Try to find by email (link existing account)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is not None:
            # Link Google to existing account
            user.google_id = google_id
            if user.auth_provider == "local":
                user.auth_provider = "local+google"
        else:
            # Check if any users exist (first user gets ADMIN)
            user_count = await db.scalar(select(func.count()).select_from(User))
            role = Role.ADMIN if user_count == 0 else Role.VIEWER

            user = User(
                email=email,
                hashed_password=None,
                full_name=full_name or email.split("@")[0],
                role=role,
                auth_provider="google",
                google_id=google_id,
            )
            db.add(user)

    if not user.is_active:
        raise ValidationError("Account is deactivated.")

    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token_record)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="user_login",
        resource_type="user",
        resource_id=str(user.id),
        details={"method": "google"},
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# Invite flow
# ---------------------------------------------------------------------------

def generate_invite_token(user_id: _uuid.UUID, settings: Settings) -> str:
    """Create a JWT invite token valid for 72 hours."""
    from jose import jwt as _jwt

    expire = datetime.now(timezone.utc) + timedelta(hours=72)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "invite",
    }
    return _jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def validate_invite_token(
    db: AsyncSession,
    token: str,
    settings: Settings,
) -> User:
    """Decode an invite token and return the user if valid."""
    data = decode_token(token, settings)
    if data is None:
        raise ValidationError("Invalid or expired invite token.")

    result = await db.execute(select(User).where(User.id == data.sub))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", str(data.sub))
    return user


async def complete_invite(
    db: AsyncSession,
    token: str,
    password: str,
    settings: Settings,
) -> TokenResponse:
    """Let an invited user set their password and get tokens."""
    user = await validate_invite_token(db, token, settings)

    user.hashed_password = hash_password(password)
    user.is_active = True

    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token_record)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="invite_completed",
        resource_type="user",
        resource_id=str(user.id),
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def user_to_response_dict(user: User) -> dict:
    """Convert a User to a response dict with resolved feature_access."""
    from app.auth.features import resolve_feature_access

    features = resolve_feature_access(user.role.value, user.feature_access_json)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at,
        "feature_access": features,
        "org_id": user.org_id,
    }
