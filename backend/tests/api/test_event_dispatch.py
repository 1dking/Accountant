"""Tests for workflow event dispatch logic via /api/workflows endpoints."""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import Contact, ContactTag
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_and_activate_workflow(
    client: AsyncClient,
    user: User,
    trigger_type: str = "contact_created",
    steps: list | None = None,
    name: str = "Dispatch Test WF",
) -> str:
    """Create a workflow, activate it, and return its ID."""
    if steps is None:
        steps = [
            {
                "step_order": 1,
                "action_type": "add_tag",
                "action_config_json": '{"tag_name": "new"}',
            },
        ]
    payload = {
        "name": name,
        "description": "Test workflow for dispatch",
        "trigger_type": trigger_type,
        "trigger_config_json": "{}",
        "steps": steps,
    }
    create_resp = await client.post(
        "/api/workflows", json=payload, headers=auth_header(user)
    )
    assert create_resp.status_code == 201, create_resp.text
    wf_id = create_resp.json()["data"]["id"]

    # Activate
    toggle_resp = await client.post(
        f"/api/workflows/{wf_id}/toggle",
        json={"is_active": True},
        headers=auth_header(user),
    )
    assert toggle_resp.status_code == 200
    return wf_id


# ---------------------------------------------------------------------------
# 1. Dispatch matching
# ---------------------------------------------------------------------------


async def test_dispatch_creates_execution_for_active_workflow(
    client: AsyncClient, admin_user: User
):
    """Active workflow with matching trigger -> execution created."""
    wf_id = await _create_and_activate_workflow(
        client, admin_user, trigger_type="contact_created", name="Active Dispatch"
    )

    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["dispatched_count"] >= 1

    # Verify execution exists
    exec_resp = await client.get(
        f"/api/workflows/{wf_id}/executions",
        headers=auth_header(admin_user),
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["meta"]["total_count"] >= 1


async def test_inactive_workflow_not_triggered(
    client: AsyncClient, admin_user: User
):
    """Inactive workflow does NOT trigger on dispatch."""
    # Create but do NOT activate
    payload = {
        "name": "Inactive WF",
        "description": "Should not trigger",
        "trigger_type": "invoice_paid",
        "trigger_config_json": "{}",
        "steps": [
            {
                "step_order": 1,
                "action_type": "create_note",
                "action_config_json": '{"title": "Nope"}',
            }
        ],
    }
    create_resp = await client.post(
        "/api/workflows", json=payload, headers=auth_header(admin_user)
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["data"]["id"]
    # Workflow is_active defaults to False

    # Dispatch invoice_paid event
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "invoice_paid", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # No executions should be created for our inactive workflow
    assert data["dispatched_count"] == 0

    # Confirm no executions
    exec_resp = await client.get(
        f"/api/workflows/{wf_id}/executions",
        headers=auth_header(admin_user),
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["meta"]["total_count"] == 0


async def test_dispatch_non_matching_trigger_no_execution(
    client: AsyncClient, admin_user: User
):
    """Dispatch with non-matching trigger type -> no execution for our workflow."""
    wf_id = await _create_and_activate_workflow(
        client, admin_user, trigger_type="contact_created", name="Mismatch WF"
    )

    # Dispatch a completely different event type
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "proposal_signed", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    # Our workflow should have zero executions
    exec_resp = await client.get(
        f"/api/workflows/{wf_id}/executions",
        headers=auth_header(admin_user),
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["meta"]["total_count"] == 0


async def test_multiple_workflows_same_trigger_all_execute(
    client: AsyncClient, admin_user: User
):
    """Multiple workflows on same trigger -> all execute."""
    wf_id_1 = await _create_and_activate_workflow(
        client, admin_user, trigger_type="invoice_sent", name="Multi WF 1"
    )
    wf_id_2 = await _create_and_activate_workflow(
        client, admin_user, trigger_type="invoice_sent", name="Multi WF 2"
    )

    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "invoice_sent", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["dispatched_count"] >= 2

    # Both workflows should have executions
    for wf_id in (wf_id_1, wf_id_2):
        exec_resp = await client.get(
            f"/api/workflows/{wf_id}/executions",
            headers=auth_header(admin_user),
        )
        assert exec_resp.status_code == 200
        assert exec_resp.json()["meta"]["total_count"] >= 1


# ---------------------------------------------------------------------------
# 2. Action verification
# ---------------------------------------------------------------------------


async def test_add_tag_action_skipped_without_contact(
    client: AsyncClient, admin_user: User
):
    """Workflow with add_tag action dispatched without contact_id -> step completes
    with 'skipped' status (no tag to add without a contact).
    """
    wf_id = await _create_and_activate_workflow(
        client,
        admin_user,
        trigger_type="contact_created",
        name="Tag WF",
        steps=[
            {
                "step_order": 1,
                "action_type": "add_tag",
                "action_config_json": json.dumps({"tag_name": "workflow-tagged"}),
            },
        ],
    )

    # Dispatch without contact_id so add_tag is skipped (not FK error)
    resp = await client.post(
        "/api/workflows/dispatch",
        json={
            "event_type": "contact_created",
            "event_data": {},
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["dispatched_count"] >= 1

    # Verify execution was created for this workflow
    exec_resp = await client.get(
        f"/api/workflows/{wf_id}/executions",
        headers=auth_header(admin_user),
    )
    assert exec_resp.status_code == 200
    executions = exec_resp.json()["data"]
    assert len(executions) >= 1
    execution = executions[0]
    assert execution["workflow_id"] == wf_id
    assert execution["status"] == "completed"
    # The execution has steps recorded
    assert len(execution["steps"]) >= 1
    step = execution["steps"][0]
    assert step["status"] == "completed"
    # result_json should indicate skipped
    assert "skipped" in (step.get("result_json") or "")


async def test_create_note_action_logs_activity(
    client: AsyncClient, admin_user: User, sample_contact: Contact, db: AsyncSession
):
    """Workflow with create_note action -> activity logged on contact."""
    from app.contacts.models import ContactActivity

    wf_id = await _create_and_activate_workflow(
        client,
        admin_user,
        trigger_type="contact_created",
        name="Note WF",
        steps=[
            {
                "step_order": 1,
                "action_type": "create_note",
                "action_config_json": json.dumps({
                    "title": "Auto generated note",
                    "description": "Created by workflow test",
                }),
            },
        ],
    )

    resp = await client.post(
        "/api/workflows/dispatch",
        json={
            "event_type": "contact_created",
            "contact_id": str(sample_contact.id),
            "event_data": {},
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["dispatched_count"] >= 1

    # Verify activity was logged on the contact
    result = await db.execute(
        select(ContactActivity).where(
            ContactActivity.contact_id == sample_contact.id,
            ContactActivity.title == "Auto generated note",
        )
    )
    activity = result.scalar_one_or_none()
    assert activity is not None
    assert activity.description == "Created by workflow test"


# ---------------------------------------------------------------------------
# 3. Auth
# ---------------------------------------------------------------------------


async def test_only_admin_can_dispatch_manually(
    client: AsyncClient, admin_user: User, team_member_user: User, viewer_user: User
):
    """Only admin can dispatch manually; others get 403."""
    # Team member
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403

    # Viewer
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403

    # Admin succeeds
    resp = await client.post(
        "/api/workflows/dispatch",
        json={"event_type": "contact_created", "event_data": {}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
