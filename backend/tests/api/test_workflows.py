"""Tests for the /api/workflows endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_workflow(client: AsyncClient, user: User, **overrides) -> dict:
    """Helper to create a workflow and return the response data dict."""
    payload = {
        "name": overrides.get("name", "Test Workflow"),
        "description": overrides.get("description", "A test workflow"),
        "trigger_type": overrides.get("trigger_type", "contact_created"),
        "trigger_config_json": overrides.get("trigger_config_json", "{}"),
        "steps": overrides.get(
            "steps",
            [
                {
                    "step_order": 1,
                    "action_type": "add_tag",
                    "action_config_json": '{"tag_name": "new"}',
                },
                {
                    "step_order": 2,
                    "action_type": "create_note",
                    "action_config_json": '{"title": "Auto note"}',
                },
            ],
        ),
    }
    resp = await client.post(
        "/api/workflows", json=payload, headers=auth_header(user)
    )
    return resp


# ---------------------------------------------------------------------------
# 1. CRUD
# ---------------------------------------------------------------------------


async def test_create_workflow(client: AsyncClient, admin_user: User):
    """Create a workflow with steps -> 201."""
    resp = await _create_workflow(client, admin_user)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Test Workflow"
    assert data["trigger_type"] == "contact_created"
    assert data["is_active"] is False
    assert len(data["steps"]) == 2
    assert data["steps"][0]["action_type"] == "add_tag"
    assert data["steps"][1]["action_type"] == "create_note"


async def test_list_workflows(client: AsyncClient, admin_user: User):
    """List workflows -> includes workflow with execution_count and last_run_at."""
    await _create_workflow(client, admin_user, name="List Test WF")
    resp = await client.get("/api/workflows", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    items = body["data"]
    assert len(items) >= 1
    wf = next(i for i in items if i["name"] == "List Test WF")
    assert "execution_count" in wf
    assert "last_run_at" in wf


async def test_get_workflow_by_id(client: AsyncClient, admin_user: User):
    """Get workflow by ID -> includes steps."""
    create_resp = await _create_workflow(client, admin_user, name="Get By ID WF")
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/workflows/{wf_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == wf_id
    assert data["name"] == "Get By ID WF"
    assert len(data["steps"]) == 2


async def test_update_workflow(client: AsyncClient, admin_user: User):
    """Update workflow name and replace steps."""
    create_resp = await _create_workflow(client, admin_user, name="Original Name")
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/workflows/{wf_id}",
        json={
            "name": "Updated Name",
            "steps": [
                {
                    "step_order": 1,
                    "action_type": "send_email",
                    "action_config_json": '{"subject": "hi"}',
                },
            ],
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Updated Name"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["action_type"] == "send_email"


async def test_delete_workflow_admin_only(
    client: AsyncClient, admin_user: User, team_member_user: User
):
    """Delete workflow -> admin only; team_member gets 403."""
    create_resp = await _create_workflow(client, admin_user, name="To Delete")
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]

    # team_member cannot delete
    resp = await client.delete(
        f"/api/workflows/{wf_id}", headers=auth_header(team_member_user)
    )
    assert resp.status_code == 403

    # admin can delete
    resp = await client.delete(
        f"/api/workflows/{wf_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text

    # Confirm deleted
    resp = await client.get(
        f"/api/workflows/{wf_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


async def test_toggle_workflow(client: AsyncClient, admin_user: User):
    """Toggle workflow active/inactive."""
    create_resp = await _create_workflow(client, admin_user)
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["is_active"] is False

    # Activate
    resp = await client.post(
        f"/api/workflows/{wf_id}/toggle",
        json={"is_active": True},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_active"] is True

    # Deactivate
    resp = await client.post(
        f"/api/workflows/{wf_id}/toggle",
        json={"is_active": False},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


# ---------------------------------------------------------------------------
# 2. Templates
# ---------------------------------------------------------------------------


async def test_get_templates(client: AsyncClient, admin_user: User):
    """Get templates -> returns a list of template objects."""
    resp = await client.get(
        "/api/workflows/templates", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each template should have name, trigger_type, steps
    template = data[0]
    assert "name" in template
    assert "trigger_type" in template
    assert "steps" in template


# ---------------------------------------------------------------------------
# 3. Dispatch & Executions
# ---------------------------------------------------------------------------


async def test_dispatch_event_creates_execution(
    client: AsyncClient, admin_user: User
):
    """Dispatch event -> creates execution for matching active workflow."""
    # Create and activate a workflow
    create_resp = await _create_workflow(
        client, admin_user, trigger_type="contact_created"
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]

    # Activate it
    await client.post(
        f"/api/workflows/{wf_id}/toggle",
        json={"is_active": True},
        headers=auth_header(admin_user),
    )

    # Dispatch
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["dispatched_count"] >= 1
    assert len(data["execution_ids"]) >= 1


async def test_get_executions(client: AsyncClient, admin_user: User):
    """Get executions for workflow -> paginated list."""
    # Create, activate, and dispatch
    create_resp = await _create_workflow(
        client, admin_user, name="Exec WF", trigger_type="contact_created"
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]

    await client.post(
        f"/api/workflows/{wf_id}/toggle",
        json={"is_active": True},
        headers=auth_header(admin_user),
    )
    await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(admin_user),
    )

    # Get executions
    resp = await client.get(
        f"/api/workflows/{wf_id}/executions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["total_count"] >= 1
    execution = body["data"][0]
    assert execution["workflow_id"] == wf_id
    assert execution["status"] in ("completed", "running", "waiting")
    assert "steps" in execution


# ---------------------------------------------------------------------------
# 4. Auth / RBAC
# ---------------------------------------------------------------------------


async def test_team_member_can_create(
    client: AsyncClient, team_member_user: User
):
    """Team member can create workflows -> 201."""
    resp = await _create_workflow(client, team_member_user, name="TM WF")
    assert resp.status_code == 201, resp.text


async def test_client_cannot_create(client: AsyncClient, client_user: User):
    """Client cannot create workflows -> 403."""
    resp = await _create_workflow(client, client_user, name="Client WF")
    assert resp.status_code == 403


async def test_viewer_cannot_create(client: AsyncClient, viewer_user: User):
    """Viewer cannot create workflows -> 403."""
    resp = await _create_workflow(client, viewer_user, name="Viewer WF")
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list(client: AsyncClient):
    """Unauthenticated user cannot list workflows -> 401."""
    resp = await client.get("/api/workflows")
    assert resp.status_code == 401


async def test_only_admin_can_dispatch(
    client: AsyncClient, admin_user: User, team_member_user: User
):
    """Only admin can manually dispatch events."""
    # Team member cannot dispatch
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403

    # Admin can dispatch
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
