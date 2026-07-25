"""Shared 'does this user have MFA?' logic across TOTP and WebAuthn.

A user counts as MFA-enabled if they have EITHER a confirmed TOTP secret
(User.mfa_enabled) OR at least one registered passkey. The two factors are
interchangeable — this is the single source of truth used by the login flow,
the Plaid Link gate, and the link-config surface, so adding passkeys never
removes access from an existing TOTP user.

Kept dependency-light (models + sqlalchemy only) to avoid import cycles with
auth.service / plaid.router / mfa_dependencies, all of which import it.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


async def count_webauthn_credentials(db: AsyncSession, user_id: uuid.UUID) -> int:
    from app.auth.webauthn_models import WebAuthnCredential

    return (
        await db.execute(
            select(func.count(WebAuthnCredential.id)).where(
                WebAuthnCredential.user_id == user_id
            )
        )
    ).scalar() or 0


async def has_mfa(db: AsyncSession, user: User) -> bool:
    """True if the user has any second factor (TOTP or a passkey)."""
    if user.mfa_enabled:
        return True
    return (await count_webauthn_credentials(db, user.id)) > 0


async def mfa_methods(db: AsyncSession, user: User) -> list[str]:
    """Which second factors are available to this user, for the login challenge."""
    methods: list[str] = []
    if user.mfa_enabled:
        methods.append("totp")
    if (await count_webauthn_credentials(db, user.id)) > 0:
        methods.append("webauthn")
    return methods
