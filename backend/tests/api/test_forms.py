"""Tests for the /api/forms endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_form(client: AsyncClient, user: User, **overrides) -> "Response":
    """Helper to create a form and return the raw httpx response."""
    payload = {
        "name": overrides.get("name", "Contact Us"),
        "description": overrides.get("description", "Get in touch"),
        "fields_json": overrides.get(
            "fields_json",
            '[{"name":"email","type":"email","required":true},{"name":"message","type":"textarea"}]',
        ),
        "thank_you_type": overrides.get("thank_you_type", "message"),
        "thank_you_config_json": overrides.get(
            "thank_you_config_json", '{"message": "Thank you!"}'
        ),
    }
    return await client.post(
        "/api/forms", json=payload, headers=auth_header(user)
    )


# ---------------------------------------------------------------------------
# 1. CRUD
# ---------------------------------------------------------------------------


async def test_create_form(client: AsyncClient, admin_user: User):
    """Create form -> 201."""
    resp = await _create_form(client, admin_user)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Contact Us"
    assert data["is_active"] is True
    assert data["fields_json"] is not None
    assert data["thank_you_type"] == "message"


async def test_list_forms(client: AsyncClient, admin_user: User):
    """List forms -> includes form with submission_count."""
    await _create_form(client, admin_user, name="List Test Form")
    resp = await client.get("/api/forms", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    items = body["data"]
    assert len(items) >= 1
    form_item = next(i for i in items if i["name"] == "List Test Form")
    assert "submission_count" in form_item
    assert form_item["submission_count"] == 0


async def test_get_form_by_id(client: AsyncClient, admin_user: User):
    """Get form by ID."""
    create_resp = await _create_form(client, admin_user, name="Get By ID Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/forms/{form_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == form_id
    assert data["name"] == "Get By ID Form"


async def test_update_form(client: AsyncClient, admin_user: User):
    """Update form fields."""
    create_resp = await _create_form(client, admin_user, name="Original Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/forms/{form_id}",
        json={"name": "Updated Form", "description": "New description"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Updated Form"
    assert data["description"] == "New description"


async def test_delete_form_admin_only(
    client: AsyncClient, admin_user: User, team_member_user: User
):
    """Delete form -> admin only; team_member gets 403."""
    create_resp = await _create_form(client, admin_user, name="To Delete Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    # team_member cannot delete
    resp = await client.delete(
        f"/api/forms/{form_id}", headers=auth_header(team_member_user)
    )
    assert resp.status_code == 403

    # admin can delete
    resp = await client.delete(
        f"/api/forms/{form_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text

    # Confirm deleted
    resp = await client.get(
        f"/api/forms/{form_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Public endpoints
# ---------------------------------------------------------------------------


async def test_get_public_form_no_auth(client: AsyncClient, admin_user: User):
    """Get public form (no auth) -> returns form data."""
    create_resp = await _create_form(client, admin_user, name="Public Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    # Public access - no auth needed
    resp = await client.get(f"/api/forms/public/{form_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == form_id
    assert data["name"] == "Public Form"
    assert "fields_json" in data


async def test_submit_public_form_no_auth(
    client: AsyncClient, admin_user: User
):
    """Submit public form (no auth) -> 201, creates submission."""
    create_resp = await _create_form(client, admin_user, name="Submit Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/forms/public/{form_id}/submit",
        json={"data": {"email": "visitor@example.com", "message": "Hello"}},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["form_id"] == form_id
    assert "data_json" in data


async def test_submit_form_creates_contact_by_email(
    client: AsyncClient, admin_user: User
):
    """Submit form creates/matches contact by email."""
    create_resp = await _create_form(client, admin_user, name="Contact Match Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    # Submit with a new email
    resp = await client.post(
        f"/api/forms/public/{form_id}/submit",
        json={
            "data": {
                "email": "newcontact@formtest.com",
                "name": "Form Contact",
                "message": "Test",
            }
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    # Should have a contact_id assigned
    assert data["contact_id"] is not None

    # Submit again with the same email -> should match the same contact
    resp2 = await client.post(
        f"/api/forms/public/{form_id}/submit",
        json={
            "data": {
                "email": "newcontact@formtest.com",
                "message": "Second submission",
            }
        },
    )
    assert resp2.status_code == 201
    data2 = resp2.json()["data"]
    assert data2["contact_id"] == data["contact_id"]


async def test_get_submissions(client: AsyncClient, admin_user: User):
    """Get submissions for form -> paginated list."""
    create_resp = await _create_form(client, admin_user, name="Submissions Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    # Submit a couple of entries
    await client.post(
        f"/api/forms/public/{form_id}/submit",
        json={"data": {"email": "sub1@test.com"}},
    )
    await client.post(
        f"/api/forms/public/{form_id}/submit",
        json={"data": {"email": "sub2@test.com"}},
    )

    resp = await client.get(
        f"/api/forms/{form_id}/submissions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["total_count"] == 2
    assert len(body["data"]) == 2


async def test_inactive_form_public_404(client: AsyncClient, admin_user: User):
    """Inactive form returns 404 on public endpoint."""
    create_resp = await _create_form(client, admin_user, name="Inactive Form")
    assert create_resp.status_code == 201
    form_id = create_resp.json()["data"]["id"]

    # Deactivate the form
    resp = await client.put(
        f"/api/forms/{form_id}",
        json={"is_active": False},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    # Public endpoint should 404
    resp = await client.get(f"/api/forms/public/{form_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Auth / RBAC
# ---------------------------------------------------------------------------


async def test_team_member_can_create_form(
    client: AsyncClient, team_member_user: User
):
    """Team member can create forms."""
    resp = await _create_form(client, team_member_user, name="TM Form")
    assert resp.status_code == 201, resp.text


async def test_client_cannot_create_form(
    client: AsyncClient, client_user: User
):
    """Client cannot create forms -> 403."""
    resp = await _create_form(client, client_user, name="Client Form")
    assert resp.status_code == 403


async def test_viewer_cannot_create_form(
    client: AsyncClient, viewer_user: User
):
    """Viewer cannot create forms -> 403."""
    resp = await _create_form(client, viewer_user, name="Viewer Form")
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list_forms(client: AsyncClient):
    """Unauthenticated -> 401 on admin endpoints."""
    resp = await client.get("/api/forms")
    assert resp.status_code == 401
