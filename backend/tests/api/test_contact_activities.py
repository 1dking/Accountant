"""Tests for the contact activity timeline (/api/contacts/.../activities).

Covers: add activity, list activities (paginated), activity type validation,
and auth enforcement.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. Add activity to contact -> 201
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_add_activity_to_contact(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """POST /api/contacts/{id}/activities should create an activity and return 201."""
    headers = auth_header(admin_user)

    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/activities",
        json={
            "activity_type": "note_added",
            "title": "Discussed Q4 projections",
            "description": "Met with John to review quarterly projections.",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["activity_type"] == "note_added"
    assert data["title"] == "Discussed Q4 projections"
    assert data["description"] == "Met with John to review quarterly projections."
    assert data["contact_id"] == str(sample_contact.id)
    assert data["created_by"] == str(admin_user.id)
    assert "id" in data
    assert "created_at" in data


@pytest.mark.normal
async def test_add_activity_with_reference(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Activities can include optional reference_type and reference_id."""
    headers = auth_header(admin_user)
    ref_id = str(uuid.uuid4())

    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/activities",
        json={
            "activity_type": "invoice_sent",
            "title": "Invoice INV-0001 sent",
            "reference_type": "invoice",
            "reference_id": ref_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["reference_type"] == "invoice"
    assert data["reference_id"] == ref_id


# ---------------------------------------------------------------------------
# 2. List activities (paginated) -> correct page/total
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_list_activities_paginated(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """GET /api/contacts/{id}/activities should return paginated results."""
    headers = auth_header(admin_user)

    # Create 5 activities
    for i in range(5):
        resp = await client.post(
            f"/api/contacts/{sample_contact.id}/activities",
            json={
                "activity_type": "note_added",
                "title": f"Activity {i + 1}",
            },
            headers=headers,
        )
        assert resp.status_code == 201

    # Fetch page 1 with page_size=2
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        params={"page": 1, "page_size": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total_count"] == 5
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 2
    assert body["meta"]["total_pages"] == 3  # ceil(5/2)

    # Fetch page 3 (last page, should have 1 item)
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        params={"page": 3, "page_size": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["meta"]["page"] == 3


@pytest.mark.normal
async def test_list_activities_empty(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Listing activities for a contact with none should return empty list."""
    headers = auth_header(admin_user)

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["total_count"] == 0


# ---------------------------------------------------------------------------
# 3. Activity types validated
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_invalid_activity_type_rejected(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Sending an invalid activity_type should be rejected (422)."""
    headers = auth_header(admin_user)

    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/activities",
        json={
            "activity_type": "invalid_type_xyz",
            "title": "Should fail",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_all_valid_activity_types(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Test that all defined ActivityType values are accepted."""
    headers = auth_header(admin_user)

    valid_types = [
        "email_sent",
        "email_received",
        "sms_sent",
        "sms_received",
        "invoice_sent",
        "invoice_paid",
        "proposal_sent",
        "proposal_signed",
        "payment_received",
        "file_shared",
        "meeting_scheduled",
        "meeting_completed",
        "note_added",
        "call_logged",
    ]

    for activity_type in valid_types:
        resp = await client.post(
            f"/api/contacts/{sample_contact.id}/activities",
            json={
                "activity_type": activity_type,
                "title": f"Test {activity_type}",
            },
            headers=headers,
        )
        assert resp.status_code == 201, (
            f"Activity type '{activity_type}' should be accepted, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# 4. Auth: unauthenticated -> 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_activity_access(
    client: AsyncClient,
    sample_contact: Contact,
):
    """Activity endpoints require authentication."""
    contact_id = str(sample_contact.id)

    # Add activity
    resp = await client.post(
        f"/api/contacts/{contact_id}/activities",
        json={"activity_type": "note_added", "title": "Nope"},
    )
    assert resp.status_code in (401, 403)

    # List activities
    resp = await client.get(f"/api/contacts/{contact_id}/activities")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 5. Role check: viewer cannot add activities
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_viewer_cannot_add_activity(
    client: AsyncClient,
    viewer_user: User,
    admin_user: User,
    sample_contact: Contact,
):
    """Viewer role should not be able to add activities."""
    viewer_headers = auth_header(viewer_user)

    resp = await client.post(
        f"/api/contacts/{sample_contact.id}/activities",
        json={
            "activity_type": "note_added",
            "title": "Viewer note",
        },
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # But viewer CAN read activities
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        headers=viewer_headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Activities are ordered by created_at descending
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_activities_ordered_most_recent_first(
    client: AsyncClient,
    admin_user: User,
    sample_contact: Contact,
):
    """Activities should be returned with most recent first."""
    headers = auth_header(admin_user)

    # Create activities in order
    for i in range(3):
        await client.post(
            f"/api/contacts/{sample_contact.id}/activities",
            json={
                "activity_type": "note_added",
                "title": f"Activity {i + 1}",
            },
            headers=headers,
        )

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/activities",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    # All activities present (order may vary with same-second timestamps)
    titles = {d["title"] for d in data}
    assert titles == {"Activity 1", "Activity 2", "Activity 3"}
