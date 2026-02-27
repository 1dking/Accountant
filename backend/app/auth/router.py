
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.schemas import (
    TokenRefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
)
from app.auth.service import (
    authenticate_user,
    refresh_tokens,
    register_user,
    revoke_refresh_token,
)
from app.auth.utils import hash_password
from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


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
    if updates.full_name is not None:
        current_user.full_name = updates.full_name
    if updates.password is not None:
        current_user.hashed_password = hash_password(updates.password)
    await db.commit()
    await db.refresh(current_user)
    return {"data": UserResponse.model_validate(current_user)}


@router.get("/users")
async def list_users(
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return {"data": [UserResponse.model_validate(u) for u in users]}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return {"data": UserResponse.model_validate(user)}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    user.is_active = False
    await db.commit()
    return {"data": {"message": f"User {user.email} deactivated"}}
