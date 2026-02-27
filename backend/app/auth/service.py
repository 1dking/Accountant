from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, Role, User
from app.auth.schemas import TokenResponse, UserCreate
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError


async def register_user(
    db: AsyncSession,
    user_data: UserCreate,
    settings: Settings,
) -> User:
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A user with email {user_data.email} already exists.")

    # First user becomes admin
    user_count = await db.scalar(select(func.count()).select_from(User))
    role = Role.ADMIN if user_count == 0 else Role.VIEWER

    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=role,
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

    if user is None or not verify_password(password, user.hashed_password):
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

    if stored_token.expires_at < datetime.now(timezone.utc):
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
