"""Tests for the native calendar & scheduling module."""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def sample_calendar(client, admin_user):
    resp = await client.post(
        "/api/scheduling",
        json={
            "name": "Consultation",
            "calendar_type": "personal",
            "duration_minutes": 30,
            "timezone": "America/New_York",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest_asyncio.fixture()
async def round_robin_calendar(client, admin_user):
    resp = await client.post(
        "/api/scheduling",
        json={
            "name": "Team Calls",
            "calendar_type": "round_robin",
            "duration_minutes": 15,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest_asyncio.fixture()
async def sample_booking(client, admin_user, sample_calendar):
    start = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/scheduling/{sample_calendar['id']}/bookings",
        json={
            "guest_name": "John Doe",
            "guest_email": "john@example.com",
            "start_time": start,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Calendar CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_calendar(client, admin_user):
    resp = await client.post(
        "/api/scheduling",
        json={"name": "Quick Call", "duration_minutes": 15},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Quick Call"
    assert data["slug"] == "quick-call"
    assert data["duration_minutes"] == 15


@pytest.mark.asyncio
async def test_list_calendars(client, admin_user, sample_calendar):
    resp = await client.get("/api/scheduling", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_get_calendar(client, admin_user, sample_calendar):
    resp = await client.get(
        f"/api/scheduling/{sample_calendar['id']}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Consultation"


@pytest.mark.asyncio
async def test_update_calendar(client, admin_user, sample_calendar):
    resp = await client.put(
        f"/api/scheduling/{sample_calendar['id']}",
        json={"duration_minutes": 45, "buffer_minutes": 15},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["duration_minutes"] == 45
    assert data["buffer_minutes"] == 15


@pytest.mark.asyncio
async def test_delete_calendar(client, admin_user, sample_calendar):
    resp = await client.delete(
        f"/api/scheduling/{sample_calendar['id']}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member(client, admin_user, sample_calendar, team_member_user):
    resp = await client.post(
        f"/api/scheduling/{sample_calendar['id']}/members",
        json={"user_id": str(team_member_user.id), "priority": 1},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["user_id"] == str(team_member_user.id)


@pytest.mark.asyncio
async def test_list_members(client, admin_user, sample_calendar):
    resp = await client.get(
        f"/api/scheduling/{sample_calendar['id']}/members",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    # Creator is auto-added
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_remove_member(client, admin_user, sample_calendar):
    # Get members
    members_resp = await client.get(
        f"/api/scheduling/{sample_calendar['id']}/members",
        headers=auth_header(admin_user),
    )
    members = members_resp.json()["data"]
    if members:
        resp = await client.delete(
            f"/api/scheduling/{sample_calendar['id']}/members/{members[0]['id']}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_booking(client, admin_user, sample_calendar):
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    resp = await client.post(
        f"/api/scheduling/{sample_calendar['id']}/bookings",
        json={
            "guest_name": "Jane Smith",
            "guest_email": "jane@example.com",
            "guest_phone": "+1555123",
            "start_time": start,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["guest_name"] == "Jane Smith"
    assert data["status"] == "confirmed"


@pytest.mark.asyncio
async def test_list_bookings(client, admin_user, sample_calendar, sample_booking):
    resp = await client.get(
        f"/api/scheduling/{sample_calendar['id']}/bookings",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_list_all_bookings(client, admin_user, sample_booking):
    resp = await client.get(
        "/api/scheduling/bookings/all",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_cancel_booking(client, admin_user, sample_calendar, sample_booking):
    resp = await client.post(
        f"/api/scheduling/{sample_calendar['id']}/bookings/{sample_booking['id']}/cancel?reason=rescheduled",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_update_booking(client, admin_user, sample_calendar, sample_booking):
    resp = await client.put(
        f"/api/scheduling/{sample_calendar['id']}/bookings/{sample_booking['id']}",
        json={"status": "completed"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"


# ---------------------------------------------------------------------------
# Available slots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_available_slots(client, admin_user, sample_calendar):
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    resp = await client.get(
        f"/api/scheduling/{sample_calendar['id']}/slots?date={tomorrow}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    # May or may not have slots depending on day-of-week


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_calendar(client, sample_calendar):
    resp = await client.get(f"/api/scheduling/public/{sample_calendar['slug']}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Consultation"


@pytest.mark.asyncio
async def test_public_book(client, sample_calendar):
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    resp = await client.post(
        f"/api/scheduling/public/{sample_calendar['slug']}/book",
        json={
            "guest_name": "Public Guest",
            "guest_email": "guest@public.com",
            "start_time": start,
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["guest_name"] == "Public Guest"
    assert data["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Round robin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_round_robin_booking(client, admin_user, round_robin_calendar):
    start = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    resp = await client.post(
        f"/api/scheduling/{round_robin_calendar['id']}/bookings",
        json={
            "guest_name": "RR Guest",
            "guest_email": "rr@example.com",
            "start_time": start,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    # Should have assigned_user_id (the calendar creator)
    assert data["assigned_user_id"] is not None


# ---------------------------------------------------------------------------
# Contact matching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_booking_matches_contact(client, admin_user, sample_calendar, sample_contact):
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    resp = await client.post(
        f"/api/scheduling/{sample_calendar['id']}/bookings",
        json={
            "guest_name": "John Doe",
            "guest_email": sample_contact.email,
            "start_time": start,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["contact_id"] == str(sample_contact.id)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_calendar_unauthenticated(client):
    resp = await client.post(
        "/api/scheduling", json={"name": "Fail"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_calendar_viewer_forbidden(client, viewer_user):
    resp = await client.post(
        "/api/scheduling",
        json={"name": "Fail"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_calendar_non_admin_forbidden(client, team_member_user, sample_calendar):
    resp = await client.delete(
        f"/api/scheduling/{sample_calendar['id']}",
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_nonexistent_calendar(client, admin_user):
    resp = await client.get(
        f"/api/scheduling/{uuid.uuid4()}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404
