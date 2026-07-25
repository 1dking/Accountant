"""MFA endpoints: enrollment, confirmation, disable, status, and the second
step of the login flow (TOTP / recovery-code verification)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import mfa_service
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


class CodeRequest(BaseModel):
    code: str


class MfaLoginRequest(BaseModel):
    mfa_token: str
    code: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/status")
async def mfa_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": mfa_service.get_status(current_user)}


@router.post("/enroll")
async def mfa_enroll(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Begin enrollment: returns the shared secret + otpauth URI (render as QR).
    MFA is not active until /enroll/confirm succeeds."""
    return {"data": await mfa_service.start_enrollment(db, current_user)}


@router.post("/enroll/confirm")
async def mfa_enroll_confirm(
    body: CodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Confirm the first code, activate MFA, and return one-time recovery codes."""
    return {"data": await mfa_service.confirm_enrollment(db, current_user, body.code)}


@router.post("/disable")
async def mfa_disable(
    body: CodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await mfa_service.disable_mfa(db, current_user, body.code)
    return {"data": {"mfa_enabled": False}}


@router.post("/login")
async def mfa_login(
    body: MfaLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Second step of login for MFA users: exchange the pending MFA token + a
    TOTP or recovery code for real access/refresh tokens."""
    tokens = await mfa_service.complete_mfa_login(
        db, body.mfa_token, body.code, request.app.state.settings, ip=_client_ip(request)
    )
    return {"data": tokens}
