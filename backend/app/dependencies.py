
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import decode_token

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncSession:
    async with request.app.state.session_factory() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user_or_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Optional[str] = Query(None),
) -> User:
    """Authenticate via Bearer header or ?token= query parameter.

    Used for endpoints that need to work in browser contexts (img src, iframe,
    download links) where the Authorization header cannot be set.
    """
    raw_token = None
    if credentials is not None:
        raw_token = credentials.credentials
    elif token is not None:
        raw_token = token

    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token_data = decode_token(raw_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


#: Roles that inherit another role's ACTION rights.
#:
#: A MANAGER may do everything a TEAM_MEMBER may do. Its extra power — seeing its
#: direct reports' records — is a VISIBILITY statement, enforced in
#: app/core/authorization.py, not a new set of route permissions.
#:
#: Declaring the inheritance here rather than editing ~240 of the 347
#: `require_role([...])` call sites is not laziness: a hand sweep of that many
#: sites is the single likeliest way to accidentally hand MANAGER an admin-only
#: endpoint. The 61 `require_role([Role.ADMIN])` sites stay admin-only, which is
#: correct — a manager is not the agency owner.
ROLE_INHERITS: dict[Role, frozenset[Role]] = {
    Role.MANAGER: frozenset({Role.TEAM_MEMBER}),
}


def require_role(allowed_roles: list[Role]):
    """Dependency factory that checks if the current user has one of the allowed roles."""
    allowed = set(allowed_roles)
    for role, inherits in ROLE_INHERITS.items():
        if inherits & allowed:
            allowed.add(role)

    async def check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return check_role


def require_feature(feature_key: str):
    """Dependency factory: does this employee have this MODULE switched on?

    Which SECTIONS a person can open is per-user (User.feature_access_json, with
    role defaults from app/auth/features.py) — the accountant gets the cashbook,
    a VA gets the dialer, and so on.

    That system already existed and was already editable by an admin, but NOTHING
    ON THE SERVER CHECKED IT: turning a module off only hid the sidebar link, and
    the API happily kept serving the data to anyone who typed the URL. This is the
    gate that makes it real.

    Mounted once per router in main.py rather than on each of the ~350 endpoints:
        include_router(cashbook_router, prefix="/api/cashbook",
                       dependencies=[Depends(require_feature("cashbook"))])

    Note this is orthogonal to record visibility. The module gate decides whether
    you may open the Cashbook at all; ownership decides which entries you see
    inside it. Both apply.
    """
    from app.auth.features import resolve_feature_access

    async def check_feature(
        credentials: Annotated[
            Optional[HTTPAuthorizationCredentials], Depends(security_optional)
        ],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        # No token at all → pass through. Several gated routers also carry
        # deliberately PUBLIC routes: Twilio voice/SMS webhooks, the Stripe
        # webhook, public proposal signing links, guest meeting joins, published
        # pages, form submissions, invitation accepts. Those callers have no
        # token and must not be feature-gated, or inbound calls and payments would
        # start 403-ing. The endpoint's own dependency still rejects anyone who
        # needs auth, so this cannot be used to skip authentication — only to skip
        # a module check that is meaningless without a user.
        if credentials is None:
            return

        token_data = decode_token(credentials.credentials)
        if token_data is None:
            return  # invalid token: let the endpoint's own auth produce the 401

        result = await db.execute(select(User).where(User.id == token_data.sub))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return  # same — not our error to raise

        features = resolve_feature_access(user.role.value, user.feature_access_json)
        if not features.get(feature_key, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The {feature_key} module is not enabled for your account",
            )

    return check_feature
