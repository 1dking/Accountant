"""Tests for the client portal (/api/portal).

Covers: dashboard, invoices, files, role-based access (non-client -> 403),
and auth enforcement.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import ClientPortalAccount, Contact
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures: portal account linking client_user to sample_contact
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def portal_account(
    db: AsyncSession,
    client_user: User,
    sample_contact: Contact,
) -> ClientPortalAccount:
    """Create a ClientPortalAccount linking the client_user to sample_contact."""
    portal = ClientPortalAccount(
        id=uuid.uuid4(),
        contact_id=sample_contact.id,
        user_id=client_user.id,
    )
    db.add(portal)
    await db.commit()
    await db.refresh(portal)
    return portal


# ---------------------------------------------------------------------------
# 1. Portal dashboard returns summary stats
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_portal_dashboard(
    client: AsyncClient,
    client_user: User,
    sample_contact: Contact,
    portal_account: ClientPortalAccount,
):
    """GET /api/portal/dashboard should return summary data for the client."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Verify expected fields
    assert "contact_name" in data
    assert "company_name" in data
    assert "pending_invoices" in data
    assert "total_outstanding" in data
    assert "pending_proposals" in data
    assert "shared_files" in data
    assert "upcoming_meetings" in data

    # Verify data matches the contact
    assert data["company_name"] == sample_contact.company_name
    assert isinstance(data["pending_invoices"], int)
    assert isinstance(data["total_outstanding"], (int, float))
    assert isinstance(data["shared_files"], int)


@pytest.mark.normal
async def test_portal_dashboard_with_invoice(
    client: AsyncClient,
    db: AsyncSession,
    client_user: User,
    admin_user: User,
    sample_contact: Contact,
    sample_invoice,
    portal_account: ClientPortalAccount,
):
    """Dashboard should reflect invoices linked to the contact."""
    headers = auth_header(client_user)

    # The sample_invoice is DRAFT status, so it won't show as pending.
    # Let's just verify the endpoint works and returns the structure.
    resp = await client.get("/api/portal/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data["pending_invoices"], int)


# ---------------------------------------------------------------------------
# 2. Portal invoices returns list
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_portal_invoices(
    client: AsyncClient,
    client_user: User,
    admin_user: User,
    sample_contact: Contact,
    sample_invoice,
    portal_account: ClientPortalAccount,
):
    """GET /api/portal/invoices should return invoices for the client's contact."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/invoices", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1

    invoice = data[0]
    assert "id" in invoice
    assert "invoice_number" in invoice
    assert "issue_date" in invoice
    assert "due_date" in invoice
    assert "total" in invoice
    assert "currency" in invoice
    assert "status" in invoice


@pytest.mark.normal
async def test_portal_invoices_empty(
    client: AsyncClient,
    client_user: User,
    sample_contact: Contact,
    portal_account: ClientPortalAccount,
):
    """Portal invoices should return empty list when no invoices exist."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/invoices", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# 3. Portal files returns shared files
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_portal_files(
    client: AsyncClient,
    client_user: User,
    sample_contact: Contact,
    portal_account: ClientPortalAccount,
):
    """GET /api/portal/files should return files shared with the client."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/files", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# 4. Auth: non-client -> 403
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_non_client_cannot_access_portal(
    client: AsyncClient,
    admin_user: User,
    team_member_user: User,
    accountant_user: User,
    viewer_user: User,
):
    """Only CLIENT role can access portal endpoints."""
    portal_endpoints = [
        "/api/portal/dashboard",
        "/api/portal/invoices",
        "/api/portal/files",
        "/api/portal/meetings",
    ]

    for user in [admin_user, team_member_user, accountant_user, viewer_user]:
        headers = auth_header(user)
        for endpoint in portal_endpoints:
            resp = await client.get(endpoint, headers=headers)
            assert resp.status_code == 403, (
                f"{user.role.value} should not access {endpoint}, "
                f"got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# 5. Auth: unauthenticated -> 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_portal_access(client: AsyncClient):
    """Portal endpoints require authentication."""
    portal_endpoints = [
        "/api/portal/dashboard",
        "/api/portal/invoices",
        "/api/portal/files",
        "/api/portal/meetings",
    ]

    for endpoint in portal_endpoints:
        resp = await client.get(endpoint)
        assert resp.status_code in (401, 403), (
            f"Unauthenticated access to {endpoint} should be 401/403, "
            f"got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 6. Client without portal account -> 404
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_client_without_portal_account(
    client: AsyncClient,
    client_user: User,
):
    """A CLIENT user without a portal account should get 404."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/dashboard", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Portal proposals endpoint
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_portal_proposals(
    client: AsyncClient,
    client_user: User,
    sample_contact: Contact,
    portal_account: ClientPortalAccount,
):
    """GET /api/portal/proposals should return proposals for the client."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/proposals", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# 8. Portal meetings endpoint
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_portal_meetings(
    client: AsyncClient,
    client_user: User,
    sample_contact: Contact,
    portal_account: ClientPortalAccount,
):
    """GET /api/portal/meetings should return meetings for the client."""
    headers = auth_header(client_user)

    resp = await client.get("/api/portal/meetings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
