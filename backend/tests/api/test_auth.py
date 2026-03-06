"""Comprehensive tests for the auth API endpoints.

Covers registration, login, token lifecycle, profile management,
admin user management, role enforcement, rate limiting, and
malformed token rejection.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from tests.conftest import TEST_SETTINGS, auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"
LOGOUT_URL = "/api/auth/logout"
ME_URL = "/api/auth/me"
USERS_URL = "/api/auth/users"


def _clear_rate_limiter() -> None:
    """Reset the in-memory login rate limiter between tests."""
    from app.auth.router import _login_attempts

    _login_attempts.clear()


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_register_first_user_succeeds(client: AsyncClient, db: AsyncSession):
    """POST /register succeeds when no users exist and creates an ADMIN."""
    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "founder@example.com",
            "password": "SecurePass1!",
            "full_name": "First User",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    data = body["data"]
    assert data["email"] == "founder@example.com"
    assert data["full_name"] == "First User"
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.normal
async def test_register_when_users_exist_fails(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /register returns 403 when at least one user already exists."""
    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "newcomer@example.com",
            "password": "SecurePass1!",
            "full_name": "Newcomer",
        },
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.normal
async def test_register_invalid_email_rejected(client: AsyncClient, db: AsyncSession):
    """POST /register rejects a payload with an invalid email address."""
    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "not-an-email",
            "password": "SecurePass1!",
            "full_name": "Bad Email",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_register_short_password_rejected(client: AsyncClient, db: AsyncSession):
    """POST /register rejects a password shorter than 8 characters."""
    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "short@example.com",
            "password": "Ab1!",
            "full_name": "Short Pass",
        },
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_login_correct_credentials_returns_tokens(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /login with valid credentials returns access + refresh tokens."""
    _clear_rate_limiter()
    resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.critical
async def test_login_wrong_password_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /login with incorrect password returns 422 (validation error)."""
    _clear_rate_limiter()
    resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "WrongPassword99!"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.normal
async def test_login_nonexistent_email_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /login with an email that does not exist returns 422."""
    _clear_rate_limiter()
    resp = await client.post(
        LOGIN_URL,
        json={"email": "ghost@example.com", "password": "SomePass123!"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 3. Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_token_refresh_returns_new_token_pair(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /refresh with a valid refresh token returns a new token pair."""
    _clear_rate_limiter()
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    refresh_token = login_resp.json()["data"]["refresh_token"]

    resp = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token must be different from the old one (rotation)
    assert data["refresh_token"] != refresh_token


@pytest.mark.normal
async def test_refresh_with_revoked_token_fails(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /refresh with an already-used (revoked) refresh token fails."""
    _clear_rate_limiter()
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    refresh_token = login_resp.json()["data"]["refresh_token"]

    # Use the refresh token once (this revokes it)
    await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    # Try to use it again
    resp = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_refresh_with_garbage_token_fails(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /refresh with a nonsense string returns 422."""
    resp = await client.post(
        REFRESH_URL,
        json={"refresh_token": "this-is-not-a-jwt"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 4. Logout
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_logout_revokes_refresh_token(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /logout revokes the refresh token so it cannot be reused."""
    _clear_rate_limiter()
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    tokens = login_resp.json()["data"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        LOGOUT_URL,
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Refresh token should now be invalid
    refresh_resp = await client.post(
        REFRESH_URL,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 422


@pytest.mark.normal
async def test_logout_without_auth_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /logout without an Authorization header returns 401/403."""
    resp = await client.post(
        LOGOUT_URL,
        json={"refresh_token": "irrelevant"},
    )
    # HTTPBearer returns 403 when no credentials are provided
    assert resp.status_code in (401, 403), resp.text


# ---------------------------------------------------------------------------
# 5. GET /me
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_get_me_with_valid_token(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """GET /me with a valid access token returns the current user."""
    headers = auth_header(admin_user)
    resp = await client.get(ME_URL, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["email"] == "admin@test.com"
    assert data["full_name"] == "Test Admin"
    assert data["role"] == "admin"
    assert data["is_active"] is True


@pytest.mark.critical
async def test_get_me_without_token_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """GET /me without any Authorization header returns 401 or 403."""
    resp = await client.get(ME_URL)
    assert resp.status_code in (401, 403), resp.text


# ---------------------------------------------------------------------------
# 6. PUT /me (profile update)
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_update_me_name(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """PUT /me can update the user's full_name."""
    headers = auth_header(admin_user)
    resp = await client.put(
        ME_URL,
        json={"full_name": "Updated Admin Name"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["full_name"] == "Updated Admin Name"


@pytest.mark.normal
async def test_update_me_password(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """PUT /me can change the password; new password works on next login."""
    _clear_rate_limiter()
    headers = auth_header(admin_user)
    resp = await client.put(
        ME_URL,
        json={"password": "NewSecure999!"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Login with the new password should succeed
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "NewSecure999!"},
    )
    assert login_resp.status_code == 200, login_resp.text


# ---------------------------------------------------------------------------
# 7. Expired / malformed tokens
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_expired_token_returns_401(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """An expired JWT is rejected with 401."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    expired_payload = {
        "sub": str(admin_user.id),
        "role": admin_user.role.value,
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "type": "access",
    }
    expired_token = jose_jwt.encode(
        expired_payload,
        TEST_SETTINGS.secret_key,
        algorithm=TEST_SETTINGS.algorithm,
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    resp = await client.get(ME_URL, headers=headers)
    assert resp.status_code == 401, resp.text


@pytest.mark.normal
async def test_malformed_token_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """A completely invalid JWT string is rejected with 401."""
    headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    resp = await client.get(ME_URL, headers=headers)
    assert resp.status_code == 401, resp.text


@pytest.mark.normal
async def test_token_signed_with_wrong_secret_returns_401(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """A token signed with a different secret key is rejected."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    payload = {
        "sub": str(admin_user.id),
        "role": admin_user.role.value,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "type": "access",
    }
    bad_token = jose_jwt.encode(payload, "wrong-secret-key", algorithm="HS256")
    headers = {"Authorization": f"Bearer {bad_token}"}
    resp = await client.get(ME_URL, headers=headers)
    assert resp.status_code == 401, resp.text


@pytest.mark.normal
async def test_token_for_nonexistent_user_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """A well-formed token referencing a non-existent user ID returns 401."""
    from app.auth.utils import create_access_token

    fake_id = uuid.uuid4()
    token = create_access_token(fake_id, "admin", TEST_SETTINGS)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(ME_URL, headers=headers)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 8. Role-based access control
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_viewer_cannot_list_users(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """GET /users with VIEWER role returns 403."""
    headers = auth_header(viewer_user)
    resp = await client.get(USERS_URL, headers=headers)
    assert resp.status_code == 403, resp.text


@pytest.mark.normal
async def test_viewer_cannot_create_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """POST /users with VIEWER role returns 403."""
    headers = auth_header(viewer_user)
    resp = await client.post(
        USERS_URL,
        json={
            "email": "newuser@example.com",
            "password": "Password123!",
            "full_name": "New User",
            "role": "viewer",
        },
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.normal
async def test_accountant_cannot_access_admin_endpoints(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    accountant_user: User,
):
    """ACCOUNTANT role cannot access admin-only user management."""
    headers = auth_header(accountant_user)

    resp = await client.get(USERS_URL, headers=headers)
    assert resp.status_code == 403, resp.text

    resp = await client.post(
        USERS_URL,
        json={
            "email": "sneaky@example.com",
            "password": "Password123!",
            "full_name": "Sneaky",
            "role": "viewer",
        },
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 9. Admin user management (CRUD)
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_admin_can_list_users(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """GET /users as ADMIN returns a paginated list of users."""
    headers = auth_header(admin_user)
    resp = await client.get(USERS_URL, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
    assert "meta" in body


@pytest.mark.normal
async def test_admin_can_create_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /users as ADMIN creates a new user with the given role."""
    headers = auth_header(admin_user)
    resp = await client.post(
        USERS_URL,
        json={
            "email": "newaccountant@example.com",
            "password": "SecurePass1!",
            "full_name": "New Accountant",
            "role": "accountant",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["email"] == "newaccountant@example.com"
    assert data["role"] == "accountant"
    assert data["is_active"] is True


@pytest.mark.normal
async def test_admin_create_duplicate_email_fails(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /users with an already-existing email returns 409."""
    headers = auth_header(admin_user)
    resp = await client.post(
        USERS_URL,
        json={
            "email": "admin@test.com",
            "password": "SecurePass1!",
            "full_name": "Duplicate",
            "role": "viewer",
        },
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.normal
async def test_admin_can_update_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """PUT /users/{id} as ADMIN can update a user's name and email."""
    headers = auth_header(admin_user)
    resp = await client.put(
        f"{USERS_URL}/{viewer_user.id}",
        json={"full_name": "Renamed Viewer", "email": "renamed@test.com"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["full_name"] == "Renamed Viewer"
    assert data["email"] == "renamed@test.com"


@pytest.mark.normal
async def test_admin_can_change_user_role(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """PUT /users/{id}/role as ADMIN changes the target user's role."""
    headers = auth_header(admin_user)
    resp = await client.put(
        f"{USERS_URL}/{viewer_user.id}/role",
        json={"role": "accountant"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["role"] == "accountant"


@pytest.mark.normal
async def test_admin_can_deactivate_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """DELETE /users/{id} as ADMIN deactivates the user."""
    headers = auth_header(admin_user)
    resp = await client.delete(
        f"{USERS_URL}/{viewer_user.id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "deactivated" in data["message"].lower() or "viewer@test.com" in data["message"]


@pytest.mark.normal
async def test_admin_update_nonexistent_user_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """PUT /users/{id} with a non-existent ID returns 404."""
    headers = auth_header(admin_user)
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"{USERS_URL}/{fake_id}",
        json={"full_name": "Nobody"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.normal
async def test_admin_role_change_nonexistent_user_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """PUT /users/{id}/role with a non-existent ID returns 404."""
    headers = auth_header(admin_user)
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"{USERS_URL}/{fake_id}/role",
        json={"role": "viewer"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.normal
async def test_admin_deactivate_nonexistent_user_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """DELETE /users/{id} with a non-existent ID returns 404."""
    headers = auth_header(admin_user)
    fake_id = uuid.uuid4()
    resp = await client.delete(f"{USERS_URL}/{fake_id}", headers=headers)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 10. Deactivated user cannot login
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_deactivated_user_cannot_login(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """A deactivated user receives a 422 on login attempt."""
    _clear_rate_limiter()
    # Deactivate the viewer
    headers = auth_header(admin_user)
    deactivate_resp = await client.delete(
        f"{USERS_URL}/{viewer_user.id}",
        headers=headers,
    )
    assert deactivate_resp.status_code == 200

    # Attempt to login as the deactivated user
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "viewer@test.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 422, login_resp.text
    assert "deactivated" in login_resp.json()["error"]["message"].lower()


@pytest.mark.normal
async def test_deactivated_user_token_rejected(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """A token issued before deactivation is rejected by /me."""
    # Get a token while the user is still active
    viewer_headers = auth_header(viewer_user)

    # Deactivate the viewer
    admin_headers = auth_header(admin_user)
    await client.delete(f"{USERS_URL}/{viewer_user.id}", headers=admin_headers)

    # Try to use the old token
    resp = await client.get(ME_URL, headers=viewer_headers)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 11. Rate limiting on login
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_rate_limiting_blocks_brute_force(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """After 10 failed login attempts within 60s the 11th is rate-limited (429)."""
    _clear_rate_limiter()

    # Fire 10 attempts (these will be counted but not rate-limited yet)
    for i in range(10):
        resp = await client.post(
            LOGIN_URL,
            json={"email": "admin@test.com", "password": f"wrong-{i}"},
        )
        # Should be 422 (invalid credentials), NOT 429 yet
        assert resp.status_code == 422, (
            f"Attempt {i + 1}: expected 422, got {resp.status_code}"
        )

    # 11th attempt should be rate-limited
    resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "wrong-final"},
    )
    assert resp.status_code == 429, resp.text
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMITED"


@pytest.mark.normal
async def test_rate_limit_does_not_block_after_clear(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """After clearing the rate limiter, login attempts succeed again."""
    _clear_rate_limiter()

    # Exhaust rate limit
    for i in range(10):
        await client.post(
            LOGIN_URL,
            json={"email": "admin@test.com", "password": f"wrong-{i}"},
        )

    # Confirm blocked
    blocked_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "wrong-final"},
    )
    assert blocked_resp.status_code == 429

    # Clear and try again -- should no longer be rate-limited
    _clear_rate_limiter()
    resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 12. Full login-then-access flow (integration)
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_full_login_flow_integration(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Login, use access token for /me, refresh, use new token for /me."""
    _clear_rate_limiter()

    # Step 1: Login
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "admin@test.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()["data"]

    # Step 2: Access /me with the access token
    me_resp = await client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "admin@test.com"

    # Step 3: Refresh the token pair
    refresh_resp = await client.post(
        REFRESH_URL,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()["data"]

    # Step 4: Access /me with the new access token
    me_resp2 = await client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_resp2.status_code == 200
    assert me_resp2.json()["data"]["email"] == "admin@test.com"

    # Step 5: Logout using the new refresh token
    logout_resp = await client.post(
        LOGOUT_URL,
        json={"refresh_token": new_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert logout_resp.status_code == 200


# ---------------------------------------------------------------------------
# 13. Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_login_missing_fields_returns_422(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /login with missing body fields returns 422 (Pydantic validation)."""
    resp = await client.post(LOGIN_URL, json={})
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_register_missing_full_name_returns_422(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /register with missing full_name returns 422."""
    resp = await client.post(
        REGISTER_URL,
        json={"email": "nofull@example.com", "password": "ValidPass1!"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_register_empty_full_name_returns_422(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /register with empty full_name returns 422 (min_length=1)."""
    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "empty@example.com",
            "password": "ValidPass1!",
            "full_name": "",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_unauthenticated_admin_endpoints_return_error(
    client: AsyncClient,
    db: AsyncSession,
):
    """Admin endpoints without any auth header return 401/403."""
    for method, url in [
        ("GET", USERS_URL),
        ("POST", USERS_URL),
    ]:
        resp = await client.request(method, url)
        assert resp.status_code in (401, 403), (
            f"{method} {url}: expected 401/403, got {resp.status_code}"
        )


@pytest.mark.normal
async def test_admin_create_user_with_default_role(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /users without specifying role defaults to VIEWER."""
    headers = auth_header(admin_user)
    resp = await client.post(
        USERS_URL,
        json={
            "email": "defaultrole@example.com",
            "password": "ValidPass1!",
            "full_name": "Default Role User",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["role"] == "viewer"
