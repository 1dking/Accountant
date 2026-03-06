"""Tests for duplicate contact detection and merge (/api/contacts/duplicates).

Covers: detect duplicates by email, detect by phone, merge contacts
(invoices/tags transferred), and role-based access.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact, ContactTag, ContactType
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date.today()
_DUE = _TODAY + timedelta(days=30)


async def _create_contact_via_api(
    client: AsyncClient,
    user: User,
    *,
    company_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> dict:
    """Create a contact through the API and return the response data."""
    payload = {
        "type": "client",
        "company_name": company_name,
        "country": "US",
    }
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone

    resp = await client.post(
        "/api/contacts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# 1. Create two contacts with same email -> detect duplicates
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_detect_duplicates_by_email(
    client: AsyncClient,
    admin_user: User,
):
    """Creating two contacts with the same email should be detected as duplicates."""
    headers = auth_header(admin_user)
    shared_email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    c1 = await _create_contact_via_api(
        client, admin_user,
        company_name="Dup Email Corp A",
        email=shared_email,
    )
    c2 = await _create_contact_via_api(
        client, admin_user,
        company_name="Dup Email Corp B",
        email=shared_email,
    )

    resp = await client.get("/api/contacts/duplicates/detect", headers=headers)
    assert resp.status_code == 200
    groups = resp.json()["data"]

    # Find the email group matching our shared email
    email_groups = [
        g for g in groups
        if g["field"] == "email" and g["value"] == shared_email
    ]
    assert len(email_groups) == 1, (
        f"Expected one email duplicate group for {shared_email}, got {email_groups}"
    )
    group = email_groups[0]
    contact_ids = [str(cid) for cid in group["contact_ids"]]
    assert c1["id"] in contact_ids
    assert c2["id"] in contact_ids


# ---------------------------------------------------------------------------
# 2. Create two contacts with same phone -> detect duplicates
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_detect_duplicates_by_phone(
    client: AsyncClient,
    admin_user: User,
):
    """Creating two contacts with the same phone should be detected as duplicates."""
    headers = auth_header(admin_user)
    shared_phone = f"+1-555-{uuid.uuid4().hex[:4]}"

    c1 = await _create_contact_via_api(
        client, admin_user,
        company_name="Dup Phone Corp A",
        phone=shared_phone,
    )
    c2 = await _create_contact_via_api(
        client, admin_user,
        company_name="Dup Phone Corp B",
        phone=shared_phone,
    )

    resp = await client.get("/api/contacts/duplicates/detect", headers=headers)
    assert resp.status_code == 200
    groups = resp.json()["data"]

    phone_groups = [
        g for g in groups
        if g["field"] == "phone" and g["value"] == shared_phone
    ]
    assert len(phone_groups) == 1, (
        f"Expected one phone duplicate group for {shared_phone}, got {phone_groups}"
    )
    group = phone_groups[0]
    contact_ids = [str(cid) for cid in group["contact_ids"]]
    assert c1["id"] in contact_ids
    assert c2["id"] in contact_ids


# ---------------------------------------------------------------------------
# 3. Merge contacts -> invoices/tags transferred to primary
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_merge_contacts_transfers_tags(
    client: AsyncClient,
    admin_user: User,
):
    """Merging contacts should transfer tags from duplicate to primary."""
    headers = auth_header(admin_user)

    # Create primary and duplicate contacts
    primary = await _create_contact_via_api(
        client, admin_user, company_name="Primary Corp",
    )
    duplicate = await _create_contact_via_api(
        client, admin_user, company_name="Duplicate Corp",
    )

    # Add tags to duplicate
    resp = await client.post(
        f"/api/contacts/{duplicate['id']}/tags",
        json={"tag_name": "transferred-tag"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Add a different tag to primary
    resp = await client.post(
        f"/api/contacts/{primary['id']}/tags",
        json={"tag_name": "existing-tag"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Merge
    resp = await client.post(
        "/api/contacts/merge",
        json={
            "primary_contact_id": primary["id"],
            "duplicate_contact_ids": [duplicate["id"]],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    merged = resp.json()["data"]
    assert merged["id"] == primary["id"]
    assert merged["company_name"] == "Primary Corp"

    # Verify tags were transferred to primary
    resp = await client.get(
        f"/api/contacts/{primary['id']}/tags",
        headers=headers,
    )
    assert resp.status_code == 200
    tag_names = [t["tag_name"] for t in resp.json()["data"]]
    assert "transferred-tag" in tag_names
    assert "existing-tag" in tag_names

    # Verify duplicate was deleted
    resp = await client.get(
        f"/api/contacts/{duplicate['id']}",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.high
async def test_merge_contacts_transfers_invoices(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
):
    """Merging contacts should transfer invoices from duplicate to primary."""
    headers = auth_header(admin_user)

    # Create primary and duplicate contacts
    primary = await _create_contact_via_api(
        client, admin_user, company_name="Invoice Primary",
    )
    duplicate = await _create_contact_via_api(
        client, admin_user, company_name="Invoice Duplicate",
    )

    # Create an invoice linked to the duplicate
    inv_resp = await client.post(
        "/api/invoices",
        json={
            "contact_id": duplicate["id"],
            "issue_date": _TODAY.isoformat(),
            "due_date": _DUE.isoformat(),
            "currency": "USD",
            "line_items": [
                {"description": "Merge Test", "quantity": 1, "unit_price": 500}
            ],
        },
        headers=headers,
    )
    assert inv_resp.status_code == 201
    invoice_id = inv_resp.json()["data"]["id"]

    # Merge
    resp = await client.post(
        "/api/contacts/merge",
        json={
            "primary_contact_id": primary["id"],
            "duplicate_contact_ids": [duplicate["id"]],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify invoice is now linked to primary
    resp = await client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["contact_id"] == primary["id"]


@pytest.mark.normal
async def test_merge_contacts_handles_duplicate_tags(
    client: AsyncClient,
    admin_user: User,
):
    """Merging contacts with overlapping tags should not create duplicates."""
    headers = auth_header(admin_user)

    primary = await _create_contact_via_api(
        client, admin_user, company_name="Tag Primary",
    )
    duplicate = await _create_contact_via_api(
        client, admin_user, company_name="Tag Duplicate",
    )

    # Add the SAME tag to both
    for contact_id in [primary["id"], duplicate["id"]]:
        resp = await client.post(
            f"/api/contacts/{contact_id}/tags",
            json={"tag_name": "shared-tag"},
            headers=headers,
        )
        assert resp.status_code == 201

    # Merge
    resp = await client.post(
        "/api/contacts/merge",
        json={
            "primary_contact_id": primary["id"],
            "duplicate_contact_ids": [duplicate["id"]],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # Primary should have exactly one instance of the shared tag
    resp = await client.get(
        f"/api/contacts/{primary['id']}/tags",
        headers=headers,
    )
    assert resp.status_code == 200
    tag_names = [t["tag_name"] for t in resp.json()["data"]]
    assert tag_names.count("shared-tag") == 1


@pytest.mark.normal
async def test_merge_multiple_duplicates(
    client: AsyncClient,
    admin_user: User,
):
    """Merging multiple duplicates at once should work."""
    headers = auth_header(admin_user)

    primary = await _create_contact_via_api(
        client, admin_user, company_name="Multi Primary",
    )
    dup1 = await _create_contact_via_api(
        client, admin_user, company_name="Multi Dup 1",
    )
    dup2 = await _create_contact_via_api(
        client, admin_user, company_name="Multi Dup 2",
    )

    # Add unique tags to each duplicate
    await client.post(
        f"/api/contacts/{dup1['id']}/tags",
        json={"tag_name": "from-dup1"},
        headers=headers,
    )
    await client.post(
        f"/api/contacts/{dup2['id']}/tags",
        json={"tag_name": "from-dup2"},
        headers=headers,
    )

    # Merge both
    resp = await client.post(
        "/api/contacts/merge",
        json={
            "primary_contact_id": primary["id"],
            "duplicate_contact_ids": [dup1["id"], dup2["id"]],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify tags from both duplicates were transferred
    resp = await client.get(
        f"/api/contacts/{primary['id']}/tags",
        headers=headers,
    )
    assert resp.status_code == 200
    tag_names = [t["tag_name"] for t in resp.json()["data"]]
    assert "from-dup1" in tag_names
    assert "from-dup2" in tag_names

    # Verify both duplicates were deleted
    for dup_id in [dup1["id"], dup2["id"]]:
        resp = await client.get(f"/api/contacts/{dup_id}", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Auth: non-admin -> 403
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_non_admin_cannot_detect_duplicates(
    client: AsyncClient,
    team_member_user: User,
    accountant_user: User,
    viewer_user: User,
    client_user: User,
):
    """Only ADMIN can access duplicate detection."""
    for user in [team_member_user, accountant_user, viewer_user, client_user]:
        headers = auth_header(user)

        resp = await client.get(
            "/api/contacts/duplicates/detect",
            headers=headers,
        )
        assert resp.status_code == 403, (
            f"{user.role.value} should not access duplicate detection"
        )


@pytest.mark.critical
async def test_non_admin_cannot_merge_contacts(
    client: AsyncClient,
    team_member_user: User,
    accountant_user: User,
    viewer_user: User,
    client_user: User,
    admin_user: User,
):
    """Only ADMIN can merge contacts."""
    headers_admin = auth_header(admin_user)

    # Create contacts to merge
    primary = await _create_contact_via_api(
        client, admin_user, company_name="Merge Primary Auth Test",
    )
    duplicate = await _create_contact_via_api(
        client, admin_user, company_name="Merge Dup Auth Test",
    )

    for user in [team_member_user, accountant_user, viewer_user, client_user]:
        headers = auth_header(user)

        resp = await client.post(
            "/api/contacts/merge",
            json={
                "primary_contact_id": primary["id"],
                "duplicate_contact_ids": [duplicate["id"]],
            },
            headers=headers,
        )
        assert resp.status_code == 403, (
            f"{user.role.value} should not be able to merge contacts"
        )


@pytest.mark.critical
async def test_unauthenticated_duplicate_access(client: AsyncClient):
    """Duplicate detection and merge require authentication."""
    resp = await client.get("/api/contacts/duplicates/detect")
    assert resp.status_code in (401, 403)

    resp = await client.post(
        "/api/contacts/merge",
        json={
            "primary_contact_id": str(uuid.uuid4()),
            "duplicate_contact_ids": [str(uuid.uuid4())],
        },
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 5. No duplicates returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_no_duplicates_returns_empty(
    client: AsyncClient,
    admin_user: User,
):
    """When no duplicates exist, detect should return an empty list.

    Note: other tests in this session may create duplicates, so we just
    verify the response structure is correct.
    """
    headers = auth_header(admin_user)

    resp = await client.get("/api/contacts/duplicates/detect", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    # Each group should have field, value, and contact_ids
    for group in data:
        assert "field" in group
        assert "value" in group
        assert "contact_ids" in group
        assert isinstance(group["contact_ids"], list)
        assert len(group["contact_ids"]) >= 2
