"""Tests for the contact tagging system (/api/contacts/.../tags).

Covers: add tag, duplicate tag (409), remove tag, list tags for contact,
bulk tag, list all tag names, filter contacts by tag, and auth enforcement.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. Add tag to contact -> 201
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_add_tag_to_contact(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """POST /api/contacts/{id}/tags should create a tag and return 201."""
    headers = auth_header(admin_user)

    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "vip"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["tag_name"] == "vip"
    assert data["contact_id"] == str(sample_contact.id)
    assert data["created_by"] == str(admin_user.id)
    assert "id" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# 2. Add duplicate tag -> 409 ConflictError
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_add_duplicate_tag_returns_409(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Adding the same tag twice to a contact should return 409."""
    headers = auth_header(admin_user)

    # First add
    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "important"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Duplicate add
    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "important"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert error["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# 3. Remove tag -> 200
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_remove_tag(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """DELETE /api/contacts/{id}/tags/{name} removes the tag."""
    headers = auth_header(admin_user)

    # Add a tag first
    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "to-remove"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Remove it
    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}/tags/to-remove",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "Tag removed"

    # Verify it is gone
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/tags",
        headers=headers,
    )
    assert resp.status_code == 200
    tag_names = [t["tag_name"] for t in resp.json()["data"]]
    assert "to-remove" not in tag_names


# ---------------------------------------------------------------------------
# 4. List tags for contact -> returns list
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_list_tags_for_contact(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """GET /api/contacts/{id}/tags returns the correct list of tags."""
    headers = auth_header(admin_user)

    # Add multiple tags
    for tag in ["alpha", "beta", "gamma"]:
        resp = await client.post(
            f"/api/contacts/{sample_contact.id}/tags",
            json={"tag_name": tag},
            headers=headers,
        )
        assert resp.status_code == 201

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/tags",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    tag_names = [t["tag_name"] for t in data]
    # Tags are ordered by tag_name
    assert "alpha" in tag_names
    assert "beta" in tag_names
    assert "gamma" in tag_names
    assert len(data) == 3


# ---------------------------------------------------------------------------
# 5. Bulk tag multiple contacts -> returns count
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_bulk_tag_contacts(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """POST /api/contacts/bulk-tag should tag multiple contacts."""
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/contacts/bulk-tag",
        json={
            "contact_ids": [str(sample_contact.id), str(sample_vendor.id)],
            "tag_name": "bulk-tagged",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["tagged_count"] == 2

    # Verify tags on each contact
    for contact_id in [sample_contact.id, sample_vendor.id]:
        resp = await client.get(
            f"/api/contacts/{contact_id}/tags",
            headers=headers,
        )
        assert resp.status_code == 200
        tag_names = [t["tag_name"] for t in resp.json()["data"]]
        assert "bulk-tagged" in tag_names


@pytest.mark.normal
async def test_bulk_tag_skips_existing(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """Bulk tagging should skip contacts that already have the tag."""
    headers = auth_header(admin_user)

    # Tag one contact first
    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "repeat"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Now bulk tag both
    resp = await client.post(
        "/api/contacts/bulk-tag",
        json={
            "contact_ids": [str(sample_contact.id), str(sample_vendor.id)],
            "tag_name": "repeat",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    # Only the vendor should be newly tagged
    assert resp.json()["data"]["tagged_count"] == 1


# ---------------------------------------------------------------------------
# 6. List all tag names -> returns unique tags
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_list_all_tag_names(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """GET /api/contacts/tags/all returns all unique tag names."""
    headers = auth_header(admin_user)

    # Add tags across different contacts, including duplicates
    await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "shared-tag"},
        headers=headers,
    )
    await client.post(
        f"/api/contacts/{sample_vendor.id}/tags",
        json={"tag_name": "shared-tag"},
        headers=headers,
    )
    await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "unique-tag"},
        headers=headers,
    )

    resp = await client.get("/api/contacts/tags/all", headers=headers)
    assert resp.status_code == 200
    tag_names = resp.json()["data"]
    assert "shared-tag" in tag_names
    assert "unique-tag" in tag_names
    # Should be deduplicated
    assert tag_names.count("shared-tag") == 1


# ---------------------------------------------------------------------------
# 7. Filter contacts by tag
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_filter_contacts_by_tag(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
    sample_vendor: Contact,
):
    """GET /api/contacts?tag=... should filter contacts by tag."""
    headers = auth_header(admin_user)

    # Tag only the sample_contact
    await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "filterable"},
        headers=headers,
    )

    # Filter by tag
    resp = await client.get(
        "/api/contacts",
        params={"tag": "filterable"},
        headers=headers,
    )
    assert resp.status_code == 200
    items = resp.json()["data"]
    ids = [c["id"] for c in items]
    assert str(sample_contact.id) in ids
    assert str(sample_vendor.id) not in ids


# ---------------------------------------------------------------------------
# 8. Unauthenticated access -> 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_tag_access(
    client: AsyncClient,
    sample_contact: Contact,
):
    """Tag endpoints require authentication."""
    contact_id = str(sample_contact.id)

    # Add tag
    resp = await client.post(
        f"/api/contacts/{contact_id}/tags",
        json={"tag_name": "test"},
    )
    assert resp.status_code in (401, 403)

    # List tags
    resp = await client.get(f"/api/contacts/{contact_id}/tags")
    assert resp.status_code in (401, 403)

    # Remove tag
    resp = await client.delete(f"/api/contacts/{contact_id}/tags/test")
    assert resp.status_code in (401, 403)

    # Bulk tag
    resp = await client.post(
        "/api/contacts/bulk-tag",
        json={"contact_ids": [contact_id], "tag_name": "test"},
    )
    assert resp.status_code in (401, 403)

    # All tags
    resp = await client.get("/api/contacts/tags/all")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 9. Viewer cannot add/remove tags (role-based)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_viewer_cannot_modify_tags(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """Viewer role should not be able to add or remove tags."""
    viewer_headers = auth_header(viewer_user)

    # Add tag -- forbidden
    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/tags",
        json={"tag_name": "no-way"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # Remove tag -- forbidden
    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}/tags/no-way",
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # But viewer CAN list tags (read access)
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/tags",
        headers=viewer_headers,
    )
    assert resp.status_code == 200
