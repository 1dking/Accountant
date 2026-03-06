"""Comprehensive tests for the documents / Drive API endpoints.

Covers file upload, folder CRUD, folder isolation, move, trash/restore,
star toggle, folder-delete guards, auth enforcement, and search.
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "/api/documents"
FOLDERS_URL = f"{BASE_URL}/folders"


def _pdf_file(name: str = "test.pdf") -> dict:
    """Return a multipart files dict for a small in-memory PDF."""
    content = b"%PDF-1.4 test content"
    return {"file": (name, io.BytesIO(content), "application/pdf")}


# ---------------------------------------------------------------------------
# 1. Upload file
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_upload_file(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /api/documents/upload succeeds and file appears in list."""
    files = _pdf_file()
    resp = await client.post(
        f"{BASE_URL}/upload",
        files=files,
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["original_filename"] == "test.pdf"
    assert data["mime_type"] == "application/pdf"
    doc_id = data["id"]

    # Verify it appears in the document list
    list_resp = await client.get(
        BASE_URL,
        headers=auth_header(admin_user),
    )
    assert list_resp.status_code == 200, list_resp.text
    doc_ids = [d["id"] for d in list_resp.json()["data"]]
    assert doc_id in doc_ids


# ---------------------------------------------------------------------------
# 2. Create folder
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_create_folder(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """POST /api/documents/folders creates a folder visible in folder list."""
    resp = await client.post(
        FOLDERS_URL,
        json={"name": "My Folder"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    folder = resp.json()["data"]
    assert folder["name"] == "My Folder"
    folder_id = folder["id"]

    # Verify it appears in folder list
    list_resp = await client.get(
        FOLDERS_URL,
        headers=auth_header(admin_user),
    )
    assert list_resp.status_code == 200, list_resp.text
    folder_ids = [f["id"] for f in list_resp.json()["data"]]
    assert folder_id in folder_ids


# ---------------------------------------------------------------------------
# 3. Upload into folder
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_upload_into_folder(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Upload a file with folder_id and verify it belongs to that folder."""
    # Create folder
    folder_resp = await client.post(
        FOLDERS_URL,
        json={"name": "Receipts"},
        headers=auth_header(admin_user),
    )
    assert folder_resp.status_code == 201, folder_resp.text
    folder_id = folder_resp.json()["data"]["id"]

    # Upload file into folder
    files = _pdf_file("receipt.pdf")
    upload_resp = await client.post(
        f"{BASE_URL}/upload",
        files=files,
        data={"folder_id": folder_id},
        headers=auth_header(admin_user),
    )
    assert upload_resp.status_code == 201, upload_resp.text
    doc_data = upload_resp.json()["data"]
    assert doc_data["folder_id"] == folder_id


# ---------------------------------------------------------------------------
# 4. Folder shows only its files (critical isolation test)
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_folder_shows_only_its_files(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Files uploaded to folder A must NOT appear in folder B's listing."""
    headers = auth_header(admin_user)

    # Create two folders
    folder_a_resp = await client.post(
        FOLDERS_URL, json={"name": "Folder A"}, headers=headers,
    )
    folder_b_resp = await client.post(
        FOLDERS_URL, json={"name": "Folder B"}, headers=headers,
    )
    folder_a_id = folder_a_resp.json()["data"]["id"]
    folder_b_id = folder_b_resp.json()["data"]["id"]

    # Upload a file into folder A
    files = _pdf_file("only-in-a.pdf")
    upload_resp = await client.post(
        f"{BASE_URL}/upload",
        files=files,
        data={"folder_id": folder_a_id},
        headers=headers,
    )
    assert upload_resp.status_code == 201, upload_resp.text
    doc_id = upload_resp.json()["data"]["id"]

    # List folder A -- should contain the file
    list_a = await client.get(
        BASE_URL, params={"folder_id": folder_a_id}, headers=headers,
    )
    assert list_a.status_code == 200, list_a.text
    ids_a = [d["id"] for d in list_a.json()["data"]]
    assert doc_id in ids_a

    # List folder B -- should NOT contain the file
    list_b = await client.get(
        BASE_URL, params={"folder_id": folder_b_id}, headers=headers,
    )
    assert list_b.status_code == 200, list_b.text
    ids_b = [d["id"] for d in list_b.json()["data"]]
    assert doc_id not in ids_b


# ---------------------------------------------------------------------------
# 5. Move file between folders
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_move_file_between_folders(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Upload to folder A, move to folder B, verify it's now in B."""
    headers = auth_header(admin_user)

    # Create folders
    fa = await client.post(FOLDERS_URL, json={"name": "Source"}, headers=headers)
    fb = await client.post(FOLDERS_URL, json={"name": "Dest"}, headers=headers)
    folder_a_id = fa.json()["data"]["id"]
    folder_b_id = fb.json()["data"]["id"]

    # Upload into folder A
    files = _pdf_file("movable.pdf")
    upload = await client.post(
        f"{BASE_URL}/upload",
        files=files,
        data={"folder_id": folder_a_id},
        headers=headers,
    )
    doc_id = upload.json()["data"]["id"]

    # Move to folder B
    move_resp = await client.post(
        f"{BASE_URL}/{doc_id}/move",
        json={"folder_id": folder_b_id},
        headers=headers,
    )
    assert move_resp.status_code == 200, move_resp.text
    assert move_resp.json()["data"]["folder_id"] == folder_b_id

    # Confirm folder B now has the file
    list_b = await client.get(
        BASE_URL, params={"folder_id": folder_b_id}, headers=headers,
    )
    ids_b = [d["id"] for d in list_b.json()["data"]]
    assert doc_id in ids_b

    # Confirm folder A no longer has the file
    list_a = await client.get(
        BASE_URL, params={"folder_id": folder_a_id}, headers=headers,
    )
    ids_a = [d["id"] for d in list_a.json()["data"]]
    assert doc_id not in ids_a


# ---------------------------------------------------------------------------
# 6. Trash and restore
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_trash_and_restore(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Soft-delete a document, verify it's trashed, then restore it."""
    headers = auth_header(admin_user)

    # Upload
    files = _pdf_file("trashable.pdf")
    upload = await client.post(
        f"{BASE_URL}/upload", files=files, headers=headers,
    )
    doc_id = upload.json()["data"]["id"]

    # Trash (soft-delete via POST /{id}/trash)
    trash_resp = await client.post(
        f"{BASE_URL}/{doc_id}/trash", headers=headers,
    )
    assert trash_resp.status_code == 200, trash_resp.text
    assert trash_resp.json()["data"]["is_trashed"] is True

    # Confirm it no longer appears in the main list (trashed docs excluded)
    list_resp = await client.get(BASE_URL, headers=headers)
    assert doc_id not in [d["id"] for d in list_resp.json()["data"]]

    # Restore
    restore_resp = await client.post(
        f"{BASE_URL}/{doc_id}/restore", headers=headers,
    )
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["data"]["is_trashed"] is False

    # Confirm it reappears in the main list
    list_resp2 = await client.get(BASE_URL, headers=headers)
    assert doc_id in [d["id"] for d in list_resp2.json()["data"]]


# ---------------------------------------------------------------------------
# 7. Star toggle
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_star_toggle(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Star a document, verify starred, then unstar."""
    headers = auth_header(admin_user)

    # Upload
    files = _pdf_file("starrable.pdf")
    upload = await client.post(
        f"{BASE_URL}/upload", files=files, headers=headers,
    )
    doc_id = upload.json()["data"]["id"]

    # Star
    star_resp = await client.post(
        f"{BASE_URL}/{doc_id}/star",
        json={"starred": True},
        headers=headers,
    )
    assert star_resp.status_code == 200, star_resp.text
    assert star_resp.json()["data"]["is_starred"] is True

    # Unstar
    unstar_resp = await client.post(
        f"{BASE_URL}/{doc_id}/star",
        json={"starred": False},
        headers=headers,
    )
    assert unstar_resp.status_code == 200, unstar_resp.text
    assert unstar_resp.json()["data"]["is_starred"] is False


# ---------------------------------------------------------------------------
# 8. Delete folder with documents returns 409
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_delete_folder_with_documents_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Deleting a folder that contains documents must return 409 Conflict."""
    headers = auth_header(admin_user)

    # Create folder
    folder = await client.post(
        FOLDERS_URL, json={"name": "Non-Empty"}, headers=headers,
    )
    folder_id = folder.json()["data"]["id"]

    # Upload file into it
    files = _pdf_file("guarded.pdf")
    await client.post(
        f"{BASE_URL}/upload",
        files=files,
        data={"folder_id": folder_id},
        headers=headers,
    )

    # Attempt to delete the folder -- should be blocked
    del_resp = await client.delete(
        f"{FOLDERS_URL}/{folder_id}", headers=headers,
    )
    assert del_resp.status_code == 409, del_resp.text


# ---------------------------------------------------------------------------
# 9. Delete empty folder succeeds
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_delete_empty_folder_succeeds(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Deleting an empty folder succeeds with 200."""
    headers = auth_header(admin_user)

    # Create folder
    folder = await client.post(
        FOLDERS_URL, json={"name": "Temp Empty"}, headers=headers,
    )
    folder_id = folder.json()["data"]["id"]

    # Delete it
    del_resp = await client.delete(
        f"{FOLDERS_URL}/{folder_id}", headers=headers,
    )
    assert del_resp.status_code == 200, del_resp.text

    # Verify it's gone from the folder list
    list_resp = await client.get(FOLDERS_URL, headers=headers)
    folder_ids = [f["id"] for f in list_resp.json()["data"]]
    assert folder_id not in folder_ids


# ---------------------------------------------------------------------------
# 10. Unauthenticated upload returns 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_upload_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /upload without auth header returns 401 or 403."""
    files = _pdf_file()
    resp = await client.post(f"{BASE_URL}/upload", files=files)
    assert resp.status_code in (401, 403), resp.text


# ---------------------------------------------------------------------------
# 11. Search documents by filename
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_search_documents_by_filename(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """GET /api/documents/search?q=<term> finds documents by filename."""
    headers = auth_header(admin_user)

    # Upload a file with a distinctive name
    unique_name = f"searchable-{uuid.uuid4().hex[:8]}.pdf"
    files = _pdf_file(unique_name)
    upload = await client.post(
        f"{BASE_URL}/upload", files=files, headers=headers,
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["data"]["id"]

    # Search for part of the unique name
    search_term = unique_name.split("-")[1].split(".")[0]  # the uuid hex part
    search_resp = await client.get(
        f"{BASE_URL}/search",
        params={"q": search_term},
        headers=headers,
    )
    assert search_resp.status_code == 200, search_resp.text
    found_ids = [d["id"] for d in search_resp.json()["data"]]
    assert doc_id in found_ids
