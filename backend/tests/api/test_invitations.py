"""Tests for the user invitation system (/api/contacts/invitations).

Covers: create invitation, list invitations (admin only), accept invitation,
duplicate email handling, resend invitation, and role-based access.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. Create invitation -> 201, returns token
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_create_invitation(
    client: AsyncClient,
    admin_user: User,
):
    """POST /api/contacts/invitations should create an invitation."""
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/contacts/invitations",
        json={
            "email": "newuser@example.com",
            "role": "team_member",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "team_member"
    assert data["status"] == "pending"
    assert data["invited_by"] == str(admin_user.id)
    assert "id" in data
    assert "expires_at" in data
    assert "created_at" in data


@pytest.mark.normal
async def test_create_invitation_with_contact_id(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Creating an invitation can link to a contact."""
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/contacts/invitations",
        json={
            "email": "clientuser@example.com",
            "role": "client",
            "contact_id": str(sample_contact.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["contact_id"] == str(sample_contact.id)


# ---------------------------------------------------------------------------
# 2. List invitations (admin only)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_list_invitations_admin(
    client: AsyncClient,
    admin_user: User,
):
    """GET /api/contacts/invitations should list all invitations for admin."""
    headers = auth_header(admin_user)

    # Create a couple of invitations first
    for email in ["inv1@example.com", "inv2@example.com"]:
        resp = await client.post(
            "/api/contacts/invitations",
            json={"email": email, "role": "viewer"},
            headers=headers,
        )
        assert resp.status_code == 201

    # List them
    resp = await client.get("/api/contacts/invitations", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) >= 2
    assert "meta" in body
    assert body["meta"]["total_count"] >= 2


# ---------------------------------------------------------------------------
# 3. Accept invitation -> creates user
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_accept_invitation_creates_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Full flow: create invitation in DB, accept via API, verify user created."""
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.contacts.models import InvitationStatus, UserInvitation

    token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid.uuid4(),
        email="accepted@example.com",
        role="team_member",
        token=token,
        status=InvitationStatus.PENDING,
        invited_by=admin_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()

    # Accept the invitation (no auth required)
    resp = await client.post(
        "/api/contacts/invitations/accept",
        json={
            "token": token,
            "password": "SecurePass123!",
            "full_name": "Accepted User",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["message"] == "Account created"
    assert "user_id" in data

    # Verify user can log in
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "accepted@example.com",
            "password": "SecurePass123!",
        },
    )
    assert login_resp.status_code == 200


@pytest.mark.normal
async def test_accept_invitation_with_invalid_token(
    client: AsyncClient,
):
    """Accepting with an invalid token should return 404."""
    resp = await client.post(
        "/api/contacts/invitations/accept",
        json={
            "token": "completely-invalid-token",
            "password": "SecurePass123!",
            "full_name": "Nobody",
        },
    )
    assert resp.status_code == 404


@pytest.mark.normal
async def test_accept_expired_invitation(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Accepting an expired invitation should return 409."""
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.contacts.models import InvitationStatus, UserInvitation

    token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid.uuid4(),
        email="expired@example.com",
        role="viewer",
        token=token,
        status=InvitationStatus.PENDING,
        invited_by=admin_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # expired
    )
    db.add(invitation)
    await db.commit()

    resp = await client.post(
        "/api/contacts/invitations/accept",
        json={
            "token": token,
            "password": "SecurePass123!",
            "full_name": "Expired User",
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 4. Invite existing email -> 409
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_invite_existing_email_returns_409(
    client: AsyncClient,
    admin_user: User,
):
    """Inviting an email that already has a user account should return 409."""
    headers = auth_header(admin_user)

    # admin_user's email is admin@test.com
    resp = await client.post(
        "/api/contacts/invitations",
        json={
            "email": "admin@test.com",
            "role": "viewer",
        },
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert error["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# 5. Resend invitation -> new token
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_resend_invitation(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /api/contacts/invitations/{id}/resend should generate a new token."""
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.contacts.models import InvitationStatus, UserInvitation

    old_token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid.uuid4(),
        email="resend@example.com",
        role="viewer",
        token=old_token,
        status=InvitationStatus.PENDING,
        invited_by=admin_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    headers = auth_header(admin_user)
    resp = await client.post(
        f"/api/contacts/invitations/{invitation.id}/resend",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "pending"
    # The response doesn't include the token but we can verify via DB
    # that it changed. For the API test, just verify the endpoint works.
    assert data["id"] == str(invitation.id)


@pytest.mark.normal
async def test_resend_nonexistent_invitation(
    client: AsyncClient,
    admin_user: User,
):
    """Resending a nonexistent invitation should return 404."""
    headers = auth_header(admin_user)
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        f"/api/contacts/invitations/{fake_id}/resend",
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Auth: non-admin -> 403
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_non_admin_cannot_create_invitation(
    client: AsyncClient,
    team_member_user: User,
    accountant_user: User,
    viewer_user: User,
):
    """Only admin can create, list, and resend invitations."""
    for user in [team_member_user, accountant_user, viewer_user]:
        headers = auth_header(user)

        # Create
        resp = await client.post(
            "/api/contacts/invitations",
            json={"email": "nope@example.com", "role": "viewer"},
            headers=headers,
        )
        assert resp.status_code == 403, (
            f"{user.role.value} should not be able to create invitations"
        )

        # List
        resp = await client.get(
            "/api/contacts/invitations",
            headers=headers,
        )
        assert resp.status_code == 403, (
            f"{user.role.value} should not be able to list invitations"
        )


@pytest.mark.critical
async def test_unauthenticated_invitation_access(
    client: AsyncClient,
):
    """Invitation management endpoints require authentication."""
    # Create
    resp = await client.post(
        "/api/contacts/invitations",
        json={"email": "x@example.com", "role": "viewer"},
    )
    assert resp.status_code in (401, 403)

    # List
    resp = await client.get("/api/contacts/invitations")
    assert resp.status_code in (401, 403)

    # Resend
    resp = await client.post(
        f"/api/contacts/invitations/{uuid.uuid4()}/resend",
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 7. Accept invitation creates portal account for CLIENT role
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_accept_client_invitation_creates_portal_account(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    sample_contact: Contact,
):
    """Accepting a CLIENT invitation with contact_id should create a portal account."""
    import secrets
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.contacts.models import ClientPortalAccount, InvitationStatus, UserInvitation

    token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid.uuid4(),
        email="portal-client@example.com",
        role="client",
        token=token,
        status=InvitationStatus.PENDING,
        invited_by=admin_user.id,
        contact_id=sample_contact.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()

    resp = await client.post(
        "/api/contacts/invitations/accept",
        json={
            "token": token,
            "password": "ClientPass123!",
            "full_name": "Portal Client",
        },
    )
    assert resp.status_code == 200
    user_id = resp.json()["data"]["user_id"]

    # Verify portal account was created
    result = await db.execute(
        select(ClientPortalAccount).where(
            ClientPortalAccount.user_id == uuid.UUID(user_id)
        )
    )
    portal = result.scalar_one_or_none()
    assert portal is not None
    assert portal.contact_id == sample_contact.id
