"""Comprehensive tests for the meetings API endpoints.

Covers CRUD operations, auth enforcement, meeting lifecycle (start/join/end),
and recording endpoints. LiveKit-dependent endpoints are tested for graceful
error handling since the LiveKit server is not available in the test env.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

BASE_URL = "/api/meetings"


def _meeting_payload(**overrides) -> dict:
    """Return a valid meeting creation payload, optionally overridden."""
    payload = {
        "title": "Test Meeting",
        "description": "A test meeting",
        "scheduled_start": (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat(),
        "scheduled_end": (
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).isoformat(),
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1. CRUD meeting
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_crud_meeting(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Full lifecycle: create, read, list, update, delete a meeting."""
    headers = auth_header(admin_user)

    # --- Create ---
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(),
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    meeting = create_resp.json()["data"]
    meeting_id = meeting["id"]
    assert meeting["title"] == "Test Meeting"
    assert meeting["description"] == "A test meeting"
    assert meeting["status"] == "scheduled"

    # --- Read single ---
    get_resp = await client.get(
        f"{BASE_URL}/{meeting_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["id"] == meeting_id
    assert get_resp.json()["data"]["title"] == "Test Meeting"

    # --- List ---
    list_resp = await client.get(f"{BASE_URL}/", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    listed_ids = [m["id"] for m in list_resp.json()["data"]]
    assert meeting_id in listed_ids

    # --- Update ---
    update_resp = await client.put(
        f"{BASE_URL}/{meeting_id}",
        json={"title": "Updated Meeting", "description": "Updated desc"},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()["data"]
    assert updated["title"] == "Updated Meeting"
    assert updated["description"] == "Updated desc"

    # --- Delete (cancel) ---
    del_resp = await client.delete(
        f"{BASE_URL}/{meeting_id}",
        headers=headers,
    )
    assert del_resp.status_code == 200, del_resp.text
    cancelled = del_resp.json()["data"]
    assert cancelled["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 2. Unauthenticated returns 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """All meeting endpoints require authentication (401 or 403 without token)."""
    # POST create
    resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(),
    )
    assert resp.status_code in (401, 403), f"POST create: {resp.status_code}"

    # GET list
    resp = await client.get(f"{BASE_URL}/")
    assert resp.status_code in (401, 403), f"GET list: {resp.status_code}"


# ---------------------------------------------------------------------------
# 3. Create meeting with all fields
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_create_meeting_with_all_fields(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Create a meeting populating every optional field."""
    headers = auth_header(admin_user)
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1, minutes=30)

    payload = {
        "title": "Full-Field Meeting",
        "description": "Detailed planning session",
        "scheduled_start": start_time.isoformat(),
        "scheduled_end": end_time.isoformat(),
        "record_meeting": True,
        "room_type": "group-small",
    }

    resp = await client.post(
        f"{BASE_URL}/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["title"] == "Full-Field Meeting"
    assert data["description"] == "Detailed planning session"
    assert data["record_meeting"] is True
    assert data["scheduled_end"] is not None


# ---------------------------------------------------------------------------
# 4. Start then join (or graceful error)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_start_meeting_graceful_error(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Start a meeting when LiveKit is not configured returns a graceful error.

    The test environment has no LiveKit server or API keys, so we expect an
    error response that is NOT a 500 Internal Server Error (i.e. the server
    handles the missing configuration gracefully).
    """
    headers = auth_header(admin_user)

    # Create a meeting first
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Start Test"),
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    meeting_id = create_resp.json()["data"]["id"]

    # Attempt to start the meeting
    start_resp = await client.post(
        f"{BASE_URL}/{meeting_id}/start",
        headers=headers,
    )
    # Accept any non-500 response: could be 200 (if mock works),
    # 400, 422, or 503 depending on LiveKit config handling
    assert start_resp.status_code != 500, (
        f"Start meeting returned 500 instead of a graceful error: {start_resp.text}"
    )

    # If start succeeded, try joining
    if start_resp.status_code == 200:
        join_resp = await client.post(
            f"{BASE_URL}/{meeting_id}/join",
            headers=headers,
        )
        assert join_resp.status_code != 500, (
            f"Join meeting returned 500: {join_resp.text}"
        )


# ---------------------------------------------------------------------------
# 5. Delete (cancel) meeting
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_delete_meeting(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """DELETE /api/meetings/{id} cancels the meeting."""
    headers = auth_header(admin_user)

    # Create
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="To Cancel"),
        headers=headers,
    )
    meeting_id = create_resp.json()["data"]["id"]

    # Delete (cancel)
    del_resp = await client.delete(
        f"{BASE_URL}/{meeting_id}",
        headers=headers,
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["data"]["status"] == "cancelled"

    # Verify it still exists but is cancelled
    get_resp = await client.get(
        f"{BASE_URL}/{meeting_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 6. List meetings returns results (multi-user visibility)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_list_meetings_multi_user(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    accountant_user: User,
):
    """Meetings created by admin are visible. Accountant can also create
    meetings. Both users see meetings in their respective list calls.
    """
    admin_headers = auth_header(admin_user)
    acct_headers = auth_header(accountant_user)

    # Admin creates a meeting
    admin_meeting = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Admin Meeting"),
        headers=admin_headers,
    )
    assert admin_meeting.status_code == 201, admin_meeting.text
    admin_meeting_id = admin_meeting.json()["data"]["id"]

    # Accountant creates a meeting
    acct_meeting = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Accountant Meeting"),
        headers=acct_headers,
    )
    assert acct_meeting.status_code == 201, acct_meeting.text
    acct_meeting_id = acct_meeting.json()["data"]["id"]

    # Admin lists meetings -- should see the admin's meeting
    admin_list = await client.get(f"{BASE_URL}/", headers=admin_headers)
    assert admin_list.status_code == 200, admin_list.text
    admin_ids = [m["id"] for m in admin_list.json()["data"]]
    assert admin_meeting_id in admin_ids

    # Accountant lists meetings -- should see the accountant's meeting
    acct_list = await client.get(f"{BASE_URL}/", headers=acct_headers)
    assert acct_list.status_code == 200, acct_list.text
    acct_ids = [m["id"] for m in acct_list.json()["data"]]
    assert acct_meeting_id in acct_ids


# ---------------------------------------------------------------------------
# 7. Viewer cannot create meetings (role enforcement)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_viewer_cannot_create_meeting(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    viewer_user: User,
):
    """VIEWER role should be denied meeting creation (403)."""
    headers = auth_header(viewer_user)
    resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Viewer Meeting"),
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 8. List recordings for a meeting
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_list_recordings_empty(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """GET /api/meetings/{id}/recordings returns empty list for new meeting."""
    headers = auth_header(admin_user)

    # Create meeting
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Recording Test"),
        headers=headers,
    )
    meeting_id = create_resp.json()["data"]["id"]

    # List recordings -- should be empty
    rec_resp = await client.get(
        f"{BASE_URL}/{meeting_id}/recordings",
        headers=headers,
    )
    assert rec_resp.status_code == 200, rec_resp.text
    assert rec_resp.json()["data"] == []


# ---------------------------------------------------------------------------
# 9. End meeting (graceful error when not started)
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_end_meeting_not_started(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Ending a meeting that was never started should return a graceful error."""
    headers = auth_header(admin_user)

    # Create meeting
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="End Before Start"),
        headers=headers,
    )
    meeting_id = create_resp.json()["data"]["id"]

    # Attempt to end it
    end_resp = await client.post(
        f"{BASE_URL}/{meeting_id}/end",
        headers=headers,
    )
    # Should not be 500; could be 400, 409, 422, or even 200 depending
    # on how the service handles ending a "scheduled" meeting
    assert end_resp.status_code != 500, (
        f"End meeting returned 500: {end_resp.text}"
    )


# ---------------------------------------------------------------------------
# 10. Accountant can create and manage meetings
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_accountant_can_manage_meetings(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    accountant_user: User,
):
    """ACCOUNTANT role can create, update, and cancel meetings."""
    headers = auth_header(accountant_user)

    # Create
    create_resp = await client.post(
        f"{BASE_URL}/",
        json=_meeting_payload(title="Accountant's Meeting"),
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    meeting_id = create_resp.json()["data"]["id"]

    # Update
    update_resp = await client.put(
        f"{BASE_URL}/{meeting_id}",
        json={"title": "Renamed by Accountant"},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["data"]["title"] == "Renamed by Accountant"

    # Cancel
    del_resp = await client.delete(
        f"{BASE_URL}/{meeting_id}",
        headers=headers,
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["data"]["status"] == "cancelled"
