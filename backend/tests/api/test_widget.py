"""Embeddable email-capture widget — a themed skin over the forms pipeline.

Each WidgetConfig auto-creates a hidden Form; submissions ride the
exact same forms.service.submit_via_webhook pipeline an external-site
form webhook uses, so contact creation and FORM_SUBMITTED dispatch come
for free. No CORS carve-out is needed anywhere (the widget's iframe is
same-origin to this API), so these tests focus on the config/submit
contract and the honeypot/disabled/rotation behavior instead.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import User
from app.contacts.models import Contact
from app.widget.service import get_or_create_config
from tests.conftest import auth_header


@pytest.mark.critical
async def test_get_my_widget_auto_creates(client: AsyncClient, admin_user: User):
    resp = await client.get("/api/widget/config", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["widget_key"]
    assert data["is_enabled"] is True
    assert data["mode"] == "floating"

    resp2 = await client.get("/api/widget/config", headers=auth_header(admin_user))
    assert resp2.json()["data"]["id"] == data["id"]


@pytest.mark.critical
async def test_public_config_no_auth(client: AsyncClient, admin_user: User, db):
    config = await get_or_create_config(db, admin_user)
    resp = await client.get(f"/api/widget/public/{config.widget_key}/config")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "widget_key" not in data  # never echoed back
    assert data["greeting_title"]


@pytest.mark.critical
async def test_disabled_widget_404s_publicly(client: AsyncClient, admin_user: User, db):
    config = await get_or_create_config(db, admin_user)
    await client.put("/api/widget/config", json={"is_enabled": False}, headers=auth_header(admin_user))

    resp = await client.get(f"/api/widget/public/{config.widget_key}/config")
    assert resp.status_code == 404


@pytest.mark.critical
async def test_unknown_key_404s(client: AsyncClient):
    resp = await client.get("/api/widget/public/does-not-exist/config")
    assert resp.status_code == 404


@pytest.mark.critical
async def test_submit_creates_contact(client: AsyncClient, admin_user: User, db):
    config = await get_or_create_config(db, admin_user)

    resp = await client.post(
        f"/api/widget/public/{config.widget_key}/submit",
        json={"name": "Jane Visitor", "email": "jane.visitor@example.com", "message": "Hi there"},
    )
    assert resp.status_code == 201

    contact = (
        await db.execute(select(Contact).where(Contact.email == "jane.visitor@example.com"))
    ).scalar_one_or_none()
    assert contact is not None
    assert contact.created_by == admin_user.id


@pytest.mark.critical
async def test_submit_honeypot_silently_drops(client: AsyncClient, admin_user: User, db):
    config = await get_or_create_config(db, admin_user)

    resp = await client.post(
        f"/api/widget/public/{config.widget_key}/submit",
        json={"name": "Bot", "email": "bot@example.com", "website": "http://spam.example"},
    )
    # Still 201 (never reveal the honeypot to whoever's probing it) but no contact.
    assert resp.status_code == 201
    contact = (
        await db.execute(select(Contact).where(Contact.email == "bot@example.com"))
    ).scalar_one_or_none()
    assert contact is None


@pytest.mark.critical
async def test_submit_fires_form_submitted_workflow(client: AsyncClient, admin_user: User, db):
    from app.workflows.models import ActionType, TriggerType, Workflow, WorkflowStep

    workflow = Workflow(
        name="Widget lead tag",
        trigger_type=TriggerType.FORM_SUBMITTED,
        trigger_config_json="{}",
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(workflow)
    await db.flush()
    db.add(
        WorkflowStep(
            workflow_id=workflow.id,
            step_order=0,
            action_type=ActionType.ADD_TAG,
            action_config_json='{"tag": "widget-lead"}',
        )
    )
    await db.commit()

    config = await get_or_create_config(db, admin_user)
    resp = await client.post(
        f"/api/widget/public/{config.widget_key}/submit",
        json={"name": "Workflow Test", "email": "workflow.test@example.com"},
    )
    assert resp.status_code == 201

    from app.workflows.models import WorkflowExecution

    executions = (
        await db.execute(select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow.id))
    ).scalars().all()
    assert len(executions) >= 1


@pytest.mark.high
async def test_rotate_key_invalidates_old_key(client: AsyncClient, admin_user: User, db):
    config = await get_or_create_config(db, admin_user)
    old_key = config.widget_key

    resp = await client.post("/api/widget/config/rotate-key", headers=auth_header(admin_user))
    assert resp.status_code == 200
    new_key = resp.json()["data"]["widget_key"]
    assert new_key != old_key

    old_resp = await client.get(f"/api/widget/public/{old_key}/config")
    assert old_resp.status_code == 404

    new_resp = await client.get(f"/api/widget/public/{new_key}/config")
    assert new_resp.status_code == 200


@pytest.mark.high
async def test_invalid_hex_color_rejected(client: AsyncClient, admin_user: User):
    resp = await client.put(
        "/api/widget/config", json={"button_color": "blue"}, headers=auth_header(admin_user)
    )
    assert resp.status_code == 422
