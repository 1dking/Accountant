"""Tests for the proposals API (/api/proposals).

Covers: CRUD, template CRUD, proposal actions (send/clone/decline/complete),
e-signature flow, recipients, role-based access, follow-up rules, and GHL
integration settings.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.proposals.models import ProposalRecipient
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_proposal(
    client: AsyncClient,
    user: User,
    contact_id: uuid.UUID,
    *,
    title: str = "Test Proposal",
    value: float = 5000.00,
) -> dict:
    """POST a proposal and return the response JSON ``data`` dict."""
    resp = await client.post(
        "/api/proposals",
        json={
            "contact_id": str(contact_id),
            "title": title,
            "content_json": "[]",
            "value": value,
            "recipients": [
                {"email": "signer@test.com", "name": "Test Signer", "role": "signer"}
            ],
        },
        headers={**auth_header(user), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# =========================================================================
# 1. Proposal CRUD
# =========================================================================


@pytest.mark.critical
@pytest.mark.asyncio
async def test_create_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals with idempotency key returns 201 with expected fields."""
    create_resp = await client.post(
        "/api/proposals",
        json={
            "contact_id": str(sample_contact.id),
            "title": "Test Proposal",
            "content_json": "[]",
            "value": 5000.00,
            "recipients": [
                {"email": "signer@test.com", "name": "Test Signer", "role": "signer"}
            ],
        },
        headers={**auth_header(admin_user), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert create_resp.status_code == 201, create_resp.text

    data = create_resp.json()["data"]
    assert data["title"] == "Test Proposal"
    assert Decimal(str(data["value"])) == Decimal("5000.00")
    assert data["status"] == "draft"
    assert data["currency"] == "USD"
    assert data["proposal_number"].startswith("PROP-")
    assert data["contact_id"] == str(sample_contact.id)
    assert len(data["recipients"]) == 1
    assert data["recipients"][0]["email"] == "signer@test.com"


@pytest.mark.high
@pytest.mark.asyncio
async def test_list_proposals(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET /api/proposals returns a paginated response containing created proposals."""
    await _create_proposal(client, admin_user, sample_contact.id, title="List Test A")
    await _create_proposal(client, admin_user, sample_contact.id, title="List Test B")

    resp = await client.get("/api/proposals", headers=auth_header(admin_user))
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "meta" in body
    titles = [p["title"] for p in body["data"]]
    assert "List Test A" in titles
    assert "List Test B" in titles


@pytest.mark.high
@pytest.mark.asyncio
async def test_get_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET /api/proposals/{id} returns full detail response."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.get(
        f"/api/proposals/{proposal_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["id"] == proposal_id
    assert data["title"] == "Test Proposal"
    assert "recipients" in data
    assert "activities" in data
    assert "content_json" in data


@pytest.mark.high
@pytest.mark.asyncio
async def test_update_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """PUT /api/proposals/{id} updates title and value."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.put(
        f"/api/proposals/{proposal_id}",
        json={"title": "Updated Proposal", "value": "7500.00"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["title"] == "Updated Proposal"
    assert Decimal(str(data["value"])) == Decimal("7500.00")


@pytest.mark.high
@pytest.mark.asyncio
async def test_delete_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """DELETE /api/proposals/{id} returns 200 and the proposal is gone."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.delete(
        f"/api/proposals/{proposal_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    # Verify deletion
    resp = await client.get(
        f"/api/proposals/{proposal_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
@pytest.mark.asyncio
async def test_create_proposal_unauthenticated(
    client: AsyncClient,
    sample_contact,
    admin_user: User,
):
    """POST /api/proposals without auth token returns 401."""
    resp = await client.post(
        "/api/proposals",
        json={
            "contact_id": str(sample_contact.id),
            "title": "Unauth Proposal",
            "content_json": "[]",
            "value": 1000.00,
            "recipients": [],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


# =========================================================================
# 2. Template CRUD
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_create_template(
    client: AsyncClient,
    admin_user: User,
):
    """POST /api/proposals/templates creates a template."""
    resp = await client.post(
        "/api/proposals/templates",
        json={
            "title": "Standard Template",
            "description": "A reusable template",
            "content_json": '[{"type":"text","data":{"text":"Hello"}}]',
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text

    data = resp.json()["data"]
    assert data["title"] == "Standard Template"
    assert data["description"] == "A reusable template"
    assert "id" in data


@pytest.mark.high
@pytest.mark.asyncio
async def test_list_templates(
    client: AsyncClient,
    admin_user: User,
):
    """GET /api/proposals/templates returns templates."""
    # Create a template first
    await client.post(
        "/api/proposals/templates",
        json={
            "title": "Template For Listing",
            "content_json": "[]",
        },
        headers=auth_header(admin_user),
    )

    resp = await client.get(
        "/api/proposals/templates", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert any(t["title"] == "Template For Listing" for t in body["data"])


@pytest.mark.high
@pytest.mark.asyncio
async def test_get_template(
    client: AsyncClient,
    admin_user: User,
):
    """GET /api/proposals/templates/{id} returns a single template."""
    create_resp = await client.post(
        "/api/proposals/templates",
        json={
            "title": "Detail Template",
            "content_json": "[]",
        },
        headers=auth_header(admin_user),
    )
    template_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/proposals/templates/{template_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["id"] == template_id
    assert data["title"] == "Detail Template"
    assert "content_json" in data


@pytest.mark.high
@pytest.mark.asyncio
async def test_convert_proposal_to_template(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/convert-template creates a template from a proposal."""
    created = await _create_proposal(client, admin_user, sample_contact.id, title="Convertible")
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/convert-template",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "Template" in data["title"]
    assert data["content_json"] == "[]"
    assert "id" in data


# =========================================================================
# 3. Proposal actions
# =========================================================================


@pytest.mark.critical
@pytest.mark.asyncio
async def test_send_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/send transitions status to 'sent'."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/send",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["status"] == "sent"
    assert data["sent_at"] is not None
    assert data["public_token"] is not None


@pytest.mark.high
@pytest.mark.asyncio
async def test_clone_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/clone creates a new draft proposal."""
    created = await _create_proposal(client, admin_user, sample_contact.id, title="Original")
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/clone",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["id"] != proposal_id
    assert "Original (Copy)" in data["title"]
    assert data["status"] == "draft"


@pytest.mark.high
@pytest.mark.asyncio
async def test_decline_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/decline marks proposal as declined."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/decline",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "declined"


@pytest.mark.high
@pytest.mark.asyncio
async def test_complete_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/complete marks proposal as signed/completed."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/complete",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["status"] == "signed"
    assert data["signed_at"] is not None


@pytest.mark.high
@pytest.mark.asyncio
async def test_proposal_stats(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET /api/proposals/stats returns dashboard statistics."""
    # Create a couple of proposals to seed stats
    await _create_proposal(client, admin_user, sample_contact.id, title="Stats A", value=1000.00)
    await _create_proposal(client, admin_user, sample_contact.id, title="Stats B", value=2000.00)

    resp = await client.get(
        "/api/proposals/stats", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "total_proposals" in data
    assert "draft_count" in data
    assert "sent_count" in data
    assert "viewed_count" in data
    assert "signed_count" in data
    assert "declined_count" in data
    assert "paid_count" in data
    assert "total_value" in data
    assert "signed_value" in data
    assert "paid_value" in data
    assert data["total_proposals"] >= 2


# =========================================================================
# 4. E-Signature flow
# =========================================================================


@pytest.mark.critical
@pytest.mark.asyncio
async def test_signing_page_data(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
    db: AsyncSession,
):
    """GET /api/proposals/sign/{token} returns signing page data after proposal is sent."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    # Send the proposal to generate signing tokens
    await client.post(
        f"/api/proposals/{proposal_id}/send",
        headers=auth_header(admin_user),
    )

    # Fetch the signing token from DB
    result = await db.execute(
        select(ProposalRecipient).where(
            ProposalRecipient.proposal_id == uuid.UUID(proposal_id)
        )
    )
    recipient = result.scalar_one()
    signing_token = recipient.signing_token
    assert signing_token is not None

    # Hit the public signing endpoint
    resp = await client.get(f"/api/proposals/sign/{signing_token}")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["proposal_id"] == proposal_id
    assert data["proposal_title"] == "Test Proposal"
    assert data["recipient_email"] == "signer@test.com"
    assert data["recipient_name"] == "Test Signer"
    assert data["already_signed"] is False


@pytest.mark.critical
@pytest.mark.asyncio
async def test_sign_proposal(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
    db: AsyncSession,
):
    """POST /api/proposals/sign/{token} with signature data succeeds."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    # Send
    await client.post(
        f"/api/proposals/{proposal_id}/send",
        headers=auth_header(admin_user),
    )

    # Get signing token & recipient id from DB
    result = await db.execute(
        select(ProposalRecipient).where(
            ProposalRecipient.proposal_id == uuid.UUID(proposal_id)
        )
    )
    recipient = result.scalar_one()
    signing_token = recipient.signing_token
    recipient_id = str(recipient.id)

    # Sign
    resp = await client.post(
        f"/api/proposals/sign/{signing_token}",
        json={
            "recipient_id": recipient_id,
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "signature_type": "drawn",
        },
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["signed"] is True
    assert data["all_signed"] is True
    assert data["proposal_id"] == proposal_id


@pytest.mark.critical
@pytest.mark.asyncio
async def test_sign_proposal_produces_audit_trail(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
    db: AsyncSession,
):
    """After signing, the recipient record has a SHA-256 hash, IP address, and signed_at."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    # Send
    await client.post(
        f"/api/proposals/{proposal_id}/send",
        headers=auth_header(admin_user),
    )

    # Get signing token
    result = await db.execute(
        select(ProposalRecipient).where(
            ProposalRecipient.proposal_id == uuid.UUID(proposal_id)
        )
    )
    recipient = result.scalar_one()
    signing_token = recipient.signing_token
    recipient_id = str(recipient.id)

    # Sign
    await client.post(
        f"/api/proposals/sign/{signing_token}",
        json={
            "recipient_id": recipient_id,
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "signature_type": "drawn",
        },
    )

    # Refresh recipient from DB to check audit fields
    db.expire_all()
    result = await db.execute(
        select(ProposalRecipient).where(ProposalRecipient.id == uuid.UUID(recipient_id))
    )
    updated_recipient = result.scalar_one()

    assert updated_recipient.signed_at is not None
    assert updated_recipient.document_hash is not None
    # SHA-256 hex digest is always 64 characters
    assert len(updated_recipient.document_hash) == 64
    assert updated_recipient.ip_address is not None


# =========================================================================
# 5. Recipients
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_add_recipient(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/{id}/recipients adds a new recipient."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.post(
        f"/api/proposals/{proposal_id}/recipients",
        json={
            "email": "cosigner@test.com",
            "name": "Co-Signer",
            "role": "signer",
            "signing_order": 2,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text

    data = resp.json()["data"]
    assert data["email"] == "cosigner@test.com"
    assert data["name"] == "Co-Signer"
    assert data["proposal_id"] == proposal_id


@pytest.mark.high
@pytest.mark.asyncio
async def test_remove_recipient(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """DELETE /api/proposals/{id}/recipients/{rid} removes a recipient."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    # Add a recipient to remove
    add_resp = await client.post(
        f"/api/proposals/{proposal_id}/recipients",
        json={
            "email": "removable@test.com",
            "name": "Removable Signer",
            "role": "signer",
        },
        headers=auth_header(admin_user),
    )
    assert add_resp.status_code == 201
    recipient_id = add_resp.json()["data"]["id"]

    # Remove
    resp = await client.delete(
        f"/api/proposals/{proposal_id}/recipients/{recipient_id}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200


# =========================================================================
# 6. Role-based access
# =========================================================================


@pytest.mark.critical
@pytest.mark.asyncio
async def test_viewer_cannot_create_proposal(
    client: AsyncClient,
    viewer_user: User,
    sample_contact,
):
    """Viewer role gets 403 when trying to create a proposal."""
    resp = await client.post(
        "/api/proposals",
        json={
            "contact_id": str(sample_contact.id),
            "title": "Viewer Proposal",
            "content_json": "[]",
            "value": 1000.00,
            "recipients": [],
        },
        headers={**auth_header(viewer_user), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 403


@pytest.mark.critical
@pytest.mark.asyncio
async def test_viewer_cannot_delete_proposal(
    client: AsyncClient,
    admin_user: User,
    viewer_user: User,
    sample_contact,
):
    """Viewer role gets 403 when trying to delete a proposal."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.delete(
        f"/api/proposals/{proposal_id}",
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


# =========================================================================
# 7. Follow-up rules
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_create_follow_up_rule(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/proposals/follow-ups creates a follow-up rule."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    resp = await client.post(
        "/api/proposals/follow-ups",
        json={
            "resource_type": "proposal",
            "resource_id": proposal_id,
            "trigger_event": "not_signed",
            "delay_hours": 24,
            "message_template": "Please sign the proposal.",
            "channel": "email",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text

    data = resp.json()["data"]
    assert data["resource_type"] == "proposal"
    assert data["resource_id"] == proposal_id
    assert data["trigger_event"] == "not_signed"
    assert data["delay_hours"] == 24
    assert data["is_active"] is True


@pytest.mark.high
@pytest.mark.asyncio
async def test_list_follow_ups(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET /api/proposals/follow-ups returns follow-up rules."""
    created = await _create_proposal(client, admin_user, sample_contact.id)
    proposal_id = created["id"]

    # Create a rule first
    await client.post(
        "/api/proposals/follow-ups",
        json={
            "resource_type": "proposal",
            "resource_id": proposal_id,
            "trigger_event": "not_signed",
            "delay_hours": 48,
            "channel": "email",
        },
        headers=auth_header(admin_user),
    )

    resp = await client.get(
        "/api/proposals/follow-ups", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(r["resource_id"] == proposal_id for r in data)


# =========================================================================
# 8. GHL integration
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_ghl_settings(
    client: AsyncClient,
    admin_user: User,
):
    """GET /api/proposals/ghl/settings returns the expected response shape."""
    resp = await client.get(
        "/api/proposals/ghl/settings", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "connected" in data
    assert "ghl_location_id" in data
    assert "last_sync_at" in data
    assert "sync_count" in data
    assert isinstance(data["connected"], bool)
    assert isinstance(data["sync_count"], int)
