"""Tests for the /api/contacts endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact, ContactType
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. CRUD -- create, read, list, update, delete
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_crud_full_lifecycle(client: AsyncClient, admin_user: User):
    """Create a contact, read it, list it, update it, and delete it."""
    headers = auth_header(admin_user)

    # CREATE
    payload = {
        "type": "client",
        "company_name": "CRUD Corp",
        "contact_name": "Alice",
        "email": "alice@crud.com",
        "phone": "+1-555-1234",
        "country": "CA",
    }
    resp = await client.post("/api/contacts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    contact_id = data["id"]
    assert data["company_name"] == "CRUD Corp"
    assert data["type"] == "client"
    assert data["contact_name"] == "Alice"
    assert data["email"] == "alice@crud.com"
    assert data["is_active"] is True

    # READ
    resp = await client.get(f"/api/contacts/{contact_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == contact_id

    # LIST
    resp = await client.get("/api/contacts", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    ids = [i["id"] for i in items]
    assert contact_id in ids

    # UPDATE
    resp = await client.put(
        f"/api/contacts/{contact_id}",
        json={"company_name": "CRUD Corp Updated", "email": "newalice@crud.com"},
        headers=headers,
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["company_name"] == "CRUD Corp Updated"
    assert updated["email"] == "newalice@crud.com"

    # DELETE (no linked invoices/estimates, should succeed)
    resp = await client.delete(f"/api/contacts/{contact_id}", headers=headers)
    assert resp.status_code == 200

    # Verify it is gone
    resp = await client.get(f"/api/contacts/{contact_id}", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Search contacts by name
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_search_contacts_by_name(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """Searching by company_name, contact_name, or email should filter results."""
    headers = auth_header(admin_user)

    # Search by company name substring
    resp = await client.get("/api/contacts", params={"search": "Acme"}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(c["company_name"] == "Acme Corp" for c in items)
    assert not any(c["company_name"] == "SupplyCo" for c in items)

    # Search by contact_name
    resp = await client.get("/api/contacts", params={"search": "Jane"}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(c["company_name"] == "SupplyCo" for c in items)

    # Search by email
    resp = await client.get(
        "/api/contacts", params={"search": "john@acme"}, headers=headers
    )
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(c["company_name"] == "Acme Corp" for c in items)

    # Search with no match
    resp = await client.get(
        "/api/contacts", params={"search": "NonExistent"}, headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


# ---------------------------------------------------------------------------
# 3. Filter by type and is_active
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_filter_by_type_and_is_active(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """Filtering by ?type= and ?is_active= should return matching contacts."""
    headers = auth_header(admin_user)

    # Filter by type=client
    resp = await client.get("/api/contacts", params={"type": "client"}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert all(c["type"] == "client" for c in items)
    assert any(c["company_name"] == "Acme Corp" for c in items)

    # Filter by type=vendor
    resp = await client.get("/api/contacts", params={"type": "vendor"}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert all(c["type"] == "vendor" for c in items)
    assert any(c["company_name"] == "SupplyCo" for c in items)

    # Filter by is_active=true (all fixtures are active)
    resp = await client.get(
        "/api/contacts", params={"is_active": "true"}, headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 2

    # Filter by is_active=false — should return none of the fixtures
    resp = await client.get(
        "/api/contacts", params={"is_active": "false"}, headers=headers
    )
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["data"]]
    assert str(sample_contact.id) not in ids
    assert str(sample_vendor.id) not in ids


# ---------------------------------------------------------------------------
# 4. Delete contact WITH invoices returns 409 ConflictError
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_delete_contact_with_invoices_returns_409(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_invoice,
):
    """Deleting a contact that has linked invoices must return 409."""
    headers = auth_header(admin_user)

    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}", headers=headers
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert error["code"] == "CONFLICT"
    assert "invoice" in error["message"].lower()


# ---------------------------------------------------------------------------
# 5. Delete contact WITHOUT invoices succeeds
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_delete_contact_without_invoices_succeeds(
    client: AsyncClient,
    admin_user: User,
    sample_vendor: Contact,
):
    """Deleting a vendor with no invoices or estimates should return 200."""
    headers = auth_header(admin_user)

    resp = await client.delete(
        f"/api/contacts/{sample_vendor.id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "Contact deleted"

    # Confirm it is gone
    resp = await client.get(
        f"/api/contacts/{sample_vendor.id}", headers=headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Duplicate detection / uniqueness
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_duplicate_company_name_allowed(
    client: AsyncClient, admin_user: User
):
    """The contacts module does not enforce unique company_name.

    Two contacts with the same company name are allowed (common in practice
    for different branches or entities). This test documents that behaviour.
    """
    headers = auth_header(admin_user)

    payload = {
        "type": "client",
        "company_name": "Duplicate Inc",
    }
    resp1 = await client.post("/api/contacts", json=payload, headers=headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/contacts", json=payload, headers=headers)
    assert resp2.status_code == 201

    # Both should be listed
    resp = await client.get(
        "/api/contacts", params={"search": "Duplicate Inc"}, headers=headers
    )
    duplicates = [
        c for c in resp.json()["data"] if c["company_name"] == "Duplicate Inc"
    ]
    assert len(duplicates) == 2


# ---------------------------------------------------------------------------
# 7. Unauthenticated access returns 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_access_returns_401(client: AsyncClient):
    """All contacts endpoints require authentication."""
    # No auth header at all
    resp = await client.get("/api/contacts")
    assert resp.status_code == 401 or resp.status_code == 403

    resp = await client.post("/api/contacts", json={"type": "client", "company_name": "X"})
    assert resp.status_code == 401 or resp.status_code == 403

    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/contacts/{fake_id}")
    assert resp.status_code == 401 or resp.status_code == 403

    resp = await client.put(f"/api/contacts/{fake_id}", json={"company_name": "Y"})
    assert resp.status_code == 401 or resp.status_code == 403

    resp = await client.delete(f"/api/contacts/{fake_id}")
    assert resp.status_code == 401 or resp.status_code == 403


# ---------------------------------------------------------------------------
# 8. Viewer can read but not create
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_viewer_can_read_but_not_create(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """A viewer may list and read contacts but must not create, update, or delete."""
    viewer_headers = auth_header(viewer_user)

    # READ — allowed
    resp = await client.get("/api/contacts", headers=viewer_headers)
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=viewer_headers
    )
    assert resp.status_code == 200

    # CREATE — forbidden
    resp = await client.post(
        "/api/contacts",
        json={"type": "vendor", "company_name": "ViewerCo"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # UPDATE — forbidden
    resp = await client.put(
        f"/api/contacts/{sample_contact.id}",
        json={"company_name": "Hacked"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # DELETE — forbidden (requires ADMIN role)
    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}",
        headers=viewer_headers,
    )
    assert resp.status_code == 403
