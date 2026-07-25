"""Passkey (WebAuthn) endpoints.

Management (authenticated): register a passkey, list, remove.
Login (pending-token): begin + verify an assertion as the second factor, an
interchangeable alternative to TOTP. Mounted at /api/auth/webauthn.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import mfa_service, webauthn_service
from app.auth.models import User
from app.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _log_origin(request: Request, stage: str) -> None:
    """Record the browser's Origin vs the configured RP origin. The #1 cause of
    a passkey ceremony failing is these two not matching."""
    s = request.app.state.settings
    logger.info(
        "webauthn.%s origin=%r configured_origin=%r rp_id=%r host=%r ua=%r",
        stage,
        request.headers.get("origin"),
        s.webauthn_origin,
        s.webauthn_rp_id,
        request.headers.get("host"),
        (request.headers.get("user-agent") or "")[:90],
    )


class RegisterFinishRequest(BaseModel):
    credential: dict
    device_name: str | None = None


class LoginBeginRequest(BaseModel):
    mfa_token: str


class LoginVerifyRequest(BaseModel):
    mfa_token: str
    credential: dict


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _credential_dto(c) -> dict:
    return {
        "id": str(c.id),
        "device_name": c.device_name,
        "created_at": c.created_at,
        "last_used_at": c.last_used_at,
    }


# ---------------------------------------------------------------------------
# Management (must already be authenticated to add/remove a passkey)
# ---------------------------------------------------------------------------

@router.post("/register/begin")
async def register_begin(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _log_origin(request, "register_begin")
    options = await webauthn_service.begin_registration(db, current_user, request.app.state.settings)
    return {"data": options}


@router.post("/register/finish")
async def register_finish(
    body: RegisterFinishRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _log_origin(request, "register_finish")
    row = await webauthn_service.finish_registration(
        db, current_user, body.credential, body.device_name, request.app.state.settings
    )
    return {"data": _credential_dto(row)}


@router.get("/credentials")
async def list_credentials(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    creds = await webauthn_service.list_credentials(db, current_user.id)
    return {"data": [_credential_dto(c) for c in creds]}


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await webauthn_service.remove_credential(db, current_user, credential_id)
    return {"data": {"removed": True}}


# ---------------------------------------------------------------------------
# Login second factor (pending MFA token from /api/auth/login)
# ---------------------------------------------------------------------------

async def _user_from_pending(db: AsyncSession, mfa_token: str, settings) -> User:
    user_id = mfa_service.decode_mfa_pending_token(mfa_token, settings)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session. Please log in again.",
        )
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session. Please log in again.",
        )
    return user


@router.post("/login/begin")
async def login_begin(
    body: LoginBeginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    settings = request.app.state.settings
    user = await _user_from_pending(db, body.mfa_token, settings)
    options = await webauthn_service.begin_authentication(db, user, settings)
    return {"data": options}


@router.post("/login/verify")
async def login_verify(
    body: LoginVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    settings = request.app.state.settings
    ip = _client_ip(request)
    user = await _user_from_pending(db, body.mfa_token, settings)
    await webauthn_service.verify_authentication(db, user, body.credential, settings, ip=ip)
    tokens = await mfa_service.issue_login_tokens(db, user, settings, method="webauthn", ip=ip)
    return {"data": tokens}
