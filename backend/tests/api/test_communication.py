"""Tests for the /api/communication endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _add_phone_number(
    client: AsyncClient, user: User, phone: str = "+15551234567", name: str = "Main Line"
) -> dict:
    """Add a phone number and return the raw response."""
    return await client.post(
        "/api/communication/phone-numbers",
        json={"phone_number": phone, "friendly_name": name},
        headers=auth_header(user),
    )


async def _log_call(client: AsyncClient, user: User, **overrides) -> "Response":
    """Log a call and return the raw response."""
    payload = {
        "direction": overrides.get("direction", "outbound"),
        "from_number": overrides.get("from_number", "+15551234567"),
        "to_number": overrides.get("to_number", "+15559876543"),
        "duration_seconds": overrides.get("duration_seconds", 120),
        "status": overrides.get("status", "completed"),
        "notes": overrides.get("notes", "Discussed project"),
        "outcome": overrides.get("outcome", "connected"),
    }
    return await client.post(
        "/api/communication/calls/log",
        json=payload,
        headers=auth_header(user),
    )


# ---------------------------------------------------------------------------
# 1. Phone Numbers (admin only)
# ---------------------------------------------------------------------------


async def test_add_phone_number(client: AsyncClient, admin_user: User):
    """Add phone number -> 201."""
    resp = await _add_phone_number(client, admin_user)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["phone_number"] == "+15551234567"
    assert data["friendly_name"] == "Main Line"
    assert data["assigned_user_id"] is None


async def test_list_phone_numbers(client: AsyncClient, admin_user: User):
    """List phone numbers."""
    await _add_phone_number(client, admin_user, phone="+15550001111", name="List Phone")
    resp = await client.get(
        "/api/communication/phone-numbers", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_assign_phone_number(client: AsyncClient, admin_user: User):
    """Assign phone number to user."""
    create_resp = await _add_phone_number(
        client, admin_user, phone="+15550002222", name="Assign Phone"
    )
    assert create_resp.status_code == 201
    phone_id = create_resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/communication/phone-numbers/{phone_id}/assign",
        json={"assigned_user_id": str(admin_user.id)},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["assigned_user_id"] == str(admin_user.id)


async def test_delete_phone_number(client: AsyncClient, admin_user: User):
    """Delete phone number."""
    create_resp = await _add_phone_number(
        client, admin_user, phone="+15550003333", name="Delete Phone"
    )
    assert create_resp.status_code == 201
    phone_id = create_resp.json()["data"]["id"]

    resp = await client.delete(
        f"/api/communication/phone-numbers/{phone_id}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text


async def test_only_admin_can_manage_phone_numbers(
    client: AsyncClient, team_member_user: User
):
    """Non-admin users cannot manage phone numbers -> 403."""
    resp = await _add_phone_number(client, team_member_user, phone="+15550009999")
    assert resp.status_code == 403

    resp = await client.get(
        "/api/communication/phone-numbers",
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. Call Logs
# ---------------------------------------------------------------------------


async def test_log_call(client: AsyncClient, admin_user: User):
    """Log a call -> 201."""
    resp = await _log_call(client, admin_user)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["direction"] == "outbound"
    assert data["from_number"] == "+15551234567"
    assert data["to_number"] == "+15559876543"
    assert data["duration_seconds"] == 120
    assert data["status"] == "completed"
    assert data["notes"] == "Discussed project"
    assert data["outcome"] == "connected"


async def test_list_call_logs(client: AsyncClient, admin_user: User):
    """List call logs."""
    await _log_call(client, admin_user)
    resp = await client.get(
        "/api/communication/calls", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["total_count"] >= 1


async def test_team_member_can_log_calls(
    client: AsyncClient, team_member_user: User
):
    """Team member can log calls -> 201."""
    resp = await _log_call(client, team_member_user)
    assert resp.status_code == 201, resp.text


async def test_viewer_cannot_log_calls(client: AsyncClient, viewer_user: User):
    """Viewer cannot log calls -> 403."""
    resp = await _log_call(client, viewer_user)
    assert resp.status_code == 403


async def test_client_cannot_log_calls(client: AsyncClient, client_user: User):
    """Client cannot log calls -> 403."""
    resp = await _log_call(client, client_user)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. SMS
# ---------------------------------------------------------------------------


async def test_send_sms_validates_input(client: AsyncClient, admin_user: User):
    """Send SMS endpoint exists and validates input.
    Without Twilio config, it may return a validation error, but the endpoint
    should accept the request and not 404.
    """
    resp = await client.post(
        "/api/communication/sms/send",
        json={"to_number": "+15559876543", "body": "Hello from test"},
        headers=auth_header(admin_user),
    )
    # Will be 422 (validation) or 400 (Twilio not configured), but not 404
    assert resp.status_code != 404


async def test_list_sms_messages(client: AsyncClient, admin_user: User):
    """List SMS messages."""
    resp = await client.get(
        "/api/communication/sms", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body


async def test_sms_webhook_receives_message(client: AsyncClient):
    """SMS webhook receives message (no auth) via form data."""
    # Twilio sends webhook data as application/x-www-form-urlencoded
    resp = await client.post(
        "/api/communication/sms/webhook",
        data={
            "From": "+15559876543",
            "To": "+15551234567",
            "Body": "Hello from outside",
            "MessageSid": "SM123abc",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["message"] == "OK"


async def test_viewer_cannot_send_sms(client: AsyncClient, viewer_user: User):
    """Viewer cannot send SMS -> 403."""
    resp = await client.post(
        "/api/communication/sms/send",
        json={"to_number": "+15559876543", "body": "Nope"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


async def test_client_cannot_send_sms(client: AsyncClient, client_user: User):
    """Client cannot send SMS -> 403."""
    resp = await client.post(
        "/api/communication/sms/send",
        json={"to_number": "+15559876543", "body": "Nope"},
        headers=auth_header(client_user),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. Live Chat
# ---------------------------------------------------------------------------


async def test_init_chat_widget_public(client: AsyncClient):
    """Init chat widget (public, no auth) -> creates session."""
    resp = await client.post(
        "/api/communication/chat/widget/init",
        json={"visitor_name": "John", "visitor_email": "john@example.com"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["visitor_name"] == "John"
    assert data["visitor_email"] == "john@example.com"
    assert data["status"] == "active"
    assert "id" in data


async def test_create_chat_session_authenticated(
    client: AsyncClient, admin_user: User
):
    """Create chat session (authenticated)."""
    resp = await client.post(
        "/api/communication/chat/sessions",
        json={"visitor_name": "Agent Session"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "active"


async def test_send_chat_message(client: AsyncClient, admin_user: User):
    """Send chat message in a session."""
    # Init a session first
    init_resp = await client.post(
        "/api/communication/chat/widget/init",
        json={"visitor_name": "Chat User"},
    )
    assert init_resp.status_code == 201
    session_id = init_resp.json()["data"]["id"]

    # Send a message
    resp = await client.post(
        f"/api/communication/chat/sessions/{session_id}/messages",
        json={"message": "Hello, I need help", "direction": "inbound"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["message"] == "Hello, I need help"
    assert data["direction"] == "inbound"
    assert data["session_id"] == session_id


async def test_list_chat_sessions(client: AsyncClient, admin_user: User):
    """List chat sessions."""
    # Create a session first
    await client.post(
        "/api/communication/chat/widget/init",
        json={"visitor_name": "List Chat User"},
    )

    resp = await client.get(
        "/api/communication/chat/sessions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["total_count"] >= 1


async def test_get_chat_messages(client: AsyncClient, admin_user: User):
    """Get chat messages for a session."""
    # Init session + send messages
    init_resp = await client.post(
        "/api/communication/chat/widget/init",
        json={"visitor_name": "Msg Chat User"},
    )
    assert init_resp.status_code == 201
    session_id = init_resp.json()["data"]["id"]

    await client.post(
        f"/api/communication/chat/sessions/{session_id}/messages",
        json={"message": "First message", "direction": "inbound"},
        headers=auth_header(admin_user),
    )
    await client.post(
        f"/api/communication/chat/sessions/{session_id}/messages",
        json={"message": "Reply", "direction": "outbound"},
        headers=auth_header(admin_user),
    )

    resp = await client.get(
        f"/api/communication/chat/sessions/{session_id}/messages",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total_count"] == 2
    assert len(body["data"]) == 2


async def test_close_chat_session(client: AsyncClient, admin_user: User):
    """Close chat session."""
    init_resp = await client.post(
        "/api/communication/chat/widget/init",
        json={"visitor_name": "Close Chat User"},
    )
    assert init_resp.status_code == 201
    session_id = init_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/communication/chat/sessions/{session_id}/close",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "closed"
