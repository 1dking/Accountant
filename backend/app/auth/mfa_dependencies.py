"""MFA gate dependencies.

``require_mfa_enabled`` is the hard gate placed in front of the Plaid Link flow:
no user may initiate or complete Plaid Link without a second factor. "Second
factor" means EITHER TOTP or a registered passkey (see mfa_common.has_mfa) — a
passkey and TOTP are interchangeable, so enabling one is enough. The 403 carries
a machine-readable ``code`` so the frontend can route the user into enrollment
instead of showing a dead error.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mfa_common import has_mfa
from app.auth.models import User
from app.dependencies import get_current_user, get_db


async def require_mfa_enabled(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not await has_mfa(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MFA_REQUIRED",
                "message": "Enable two-factor authentication (an authenticator app or a passkey) before connecting a bank account.",
            },
        )
    return current_user
