"""Tests for file sharing with contacts (/api/contacts/file-shares).

Covers: share file, list shares for contact, remove share, role-based
access (viewer cannot share), and auth enforcement.
"""

import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact
from app.documents.models import Document
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helper: upload a document and return its ID
# ---------------------------------------------------------------------------


async def _upload_document(client: AsyncClient, user: User) -> str:
    """Upload a test document and return its ID."""
    content = b"%PDF-1.4 test content for file sharing"
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("shared-test.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_header(user),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# 1. Share file with contact -> 201
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_share_file_with_contact(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """POST /api/contacts/file-shares should create a share and return 201."""
    doc_id = await _upload_document(client, admin_user)
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
            "permission": "view",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["file_id"] == doc_id
    assert data["contact_id"] == str(sample_contact.id)
    assert data["permission"] == "view"
    assert data["shared_by"] == str(admin_user.id)
    assert "id" in data
    assert "shared_at" in data


@pytest.mark.normal
async def test_share_file_with_download_permission(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Sharing a file with 'download' permission should work."""
    doc_id = await _upload_document(client, admin_user)
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
            "permission": "download",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["permission"] == "download"


# ---------------------------------------------------------------------------
# 2. List file shares for contact
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_list_file_shares_for_contact(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """GET /api/contacts/{id}/file-shares should return shared files."""
    headers = auth_header(admin_user)

    # Upload and share two files
    doc_id_1 = await _upload_document(client, admin_user)
    doc_id_2 = await _upload_document(client, admin_user)

    for doc_id in [doc_id_1, doc_id_2]:
        resp = await client.post(
            "/api/contacts/file-shares",
            json={
                "file_id": doc_id,
                "contact_id": str(sample_contact.id),
            },
            headers=headers,
        )
        assert resp.status_code == 201

    # List shares
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/file-shares",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    file_ids = [s["file_id"] for s in data]
    assert doc_id_1 in file_ids
    assert doc_id_2 in file_ids


@pytest.mark.normal
async def test_list_file_shares_empty(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Listing file shares for a contact with none should return empty list."""
    headers = auth_header(admin_user)

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/file-shares",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# 3. Remove file share
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_remove_file_share(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """DELETE /api/contacts/file-shares/{share_id} removes the share."""
    headers = auth_header(admin_user)

    # Upload and share
    doc_id = await _upload_document(client, admin_user)
    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    share_id = resp.json()["data"]["id"]

    # Remove the share
    resp = await client.delete(
        f"/api/contacts/file-shares/{share_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "File share removed"

    # Verify it is gone
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/file-shares",
        headers=headers,
    )
    assert resp.status_code == 200
    share_ids = [s["id"] for s in resp.json()["data"]]
    assert share_id not in share_ids


@pytest.mark.normal
async def test_remove_nonexistent_file_share_returns_404(
    client: AsyncClient,
    admin_user: User,
):
    """Removing a nonexistent file share should return 404."""
    headers = auth_header(admin_user)
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/api/contacts/file-shares/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Auth: viewer cannot share (403)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_viewer_cannot_share_file(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """Viewer role should not be able to share files."""
    # Upload as admin (viewer may not have upload perms)
    doc_id = await _upload_document(client, admin_user)
    viewer_headers = auth_header(viewer_user)

    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
        },
        headers=viewer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.normal
async def test_viewer_cannot_remove_file_share(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """Viewer role should not be able to remove file shares."""
    headers = auth_header(admin_user)

    # Admin shares a file
    doc_id = await _upload_document(client, admin_user)
    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    share_id = resp.json()["data"]["id"]

    # Viewer tries to remove
    resp = await client.delete(
        f"/api/contacts/file-shares/{share_id}",
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.normal
async def test_viewer_can_list_file_shares(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """Viewer role can read file shares (list endpoint uses get_current_user)."""
    viewer_headers = auth_header(viewer_user)

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/file-shares",
        headers=viewer_headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Auth: unauthenticated -> 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_file_share_access(
    client: AsyncClient,
    sample_contact: Contact,
):
    """File share endpoints require authentication."""
    contact_id = str(sample_contact.id)
    fake_file_id = str(uuid.uuid4())

    # Create share
    resp = await client.post(
        "/api/contacts/file-shares",
        json={"file_id": fake_file_id, "contact_id": contact_id},
    )
    assert resp.status_code in (401, 403)

    # List shares
    resp = await client.get(f"/api/contacts/{contact_id}/file-shares")
    assert resp.status_code in (401, 403)

    # Remove share
    resp = await client.delete(f"/api/contacts/file-shares/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 6. Sharing creates a FILE_SHARED activity
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_sharing_creates_activity(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Sharing a file should automatically log a 'file_shared' activity."""
    headers = auth_header(admin_user)
    doc_id = await _upload_document(client, admin_user)

    resp = await client.post(
        "/api/contacts/file-shares",
        json={
            "file_id": doc_id,
            "contact_id": str(sample_contact.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201

    # Check activities
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        headers=headers,
    )
    assert resp.status_code == 200
    activities = resp.json()["data"]
    file_shared_activities = [
        a for a in activities if a["activity_type"] == "file_shared"
    ]
    assert len(file_shared_activities) >= 1
