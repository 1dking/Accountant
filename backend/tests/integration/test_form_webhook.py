"""Inbound lead webhook — an external website posts leads into the CRM.

The app already had its own hosted forms (submit → contact), but nothing an
outside site (Webflow, WordPress, a custom form) could POST to. This adds a
per-form webhook: generate a secret URL, hand it to the external site, and its
submissions become contacts owned by the form's creator — firing FORM_SUBMITTED
automations along the way.
"""
import json
import uuid

import pytest
from sqlalchemy import select

from app.auth.models import Role, User
from app.contacts.models import Contact
from app.forms.models import Form, FormSubmission
from tests.conftest import auth_header


async def _make_form(db, owner: User, active: bool = True) -> Form:
    form = Form(
        id=uuid.uuid4(),
        name="Website Contact Form",
        fields_json=json.dumps([{"name": "email", "type": "email"}]),
        is_active=active,
        created_by=owner.id,
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form


@pytest.mark.high
async def test_generate_webhook_key_returns_a_usable_url(
    client, db, admin_user: User
):
    form = await _make_form(db, admin_user)

    resp = await client.post(
        f"/api/forms/{form.id}/webhook-key", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["webhook_key"]
    assert data["webhook_url"].endswith(f"/api/forms/webhook/{data['webhook_key']}")


@pytest.mark.high
async def test_rotating_the_key_invalidates_the_old_one(client, db, admin_user: User):
    form = await _make_form(db, admin_user)

    first = (
        await client.post(
            f"/api/forms/{form.id}/webhook-key", headers=auth_header(admin_user)
        )
    ).json()["data"]["webhook_key"]
    second = (
        await client.post(
            f"/api/forms/{form.id}/webhook-key", headers=auth_header(admin_user)
        )
    ).json()["data"]["webhook_key"]

    assert first != second
    # The old key no longer works.
    old = await client.post(
        f"/api/forms/webhook/{first}", json={"email": "x@y.com"}
    )
    assert old.status_code == 404


@pytest.mark.critical
async def test_external_lead_becomes_a_contact_owned_by_the_form_creator(
    client, db, team_member_user: User
):
    """The core behaviour: a raw POST from a website creates a CRM contact, owned
    by whoever made the form (records are private)."""
    form = await _make_form(db, team_member_user)
    key = form.webhook_key = "test-key-fixed-123"
    await db.commit()

    # No auth header — the key in the URL is the credential. Messy external field
    # names, exactly as a real site would send.
    resp = await client.post(
        f"/api/forms/webhook/{key}",
        json={
            "Email Address": "lead@bigco.com",
            "Full Name": "Dana Lead",
            "Phone Number": "+15551234567",
            "Company Name": "BigCo",
            "Message": "Interested in your services",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["received"] is True

    contact = (
        await db.execute(select(Contact).where(Contact.email == "lead@bigco.com"))
    ).scalar_one()
    assert contact.contact_name == "Dana Lead"
    assert contact.phone == "+15551234567"
    assert contact.company_name == "BigCo"
    assert contact.created_by == team_member_user.id, "owned by the form's creator"
    assert contact.lead_source == "webhook"

    # The full raw payload is retained on the submission.
    sub = (
        await db.execute(select(FormSubmission).where(FormSubmission.form_id == form.id))
    ).scalar_one()
    assert sub.contact_id == contact.id
    assert json.loads(sub.data_json)["Message"] == "Interested in your services"


@pytest.mark.critical
async def test_a_repeat_lead_matches_the_existing_contact(
    client, db, admin_user: User
):
    """Same email twice must not create two contacts."""
    form = await _make_form(db, admin_user)
    form.webhook_key = "repeat-key"
    await db.commit()

    for _ in range(2):
        r = await client.post(
            f"/api/forms/webhook/repeat-key", json={"email": "repeat@x.com", "name": "Repeat"}
        )
        assert r.status_code == 201

    contacts = (
        await db.execute(select(Contact).where(Contact.email == "repeat@x.com"))
    ).scalars().all()
    assert len(contacts) == 1, "a repeat lead must match, not duplicate"

    subs = (
        await db.execute(select(FormSubmission).where(FormSubmission.form_id == form.id))
    ).scalars().all()
    assert len(subs) == 2, "but each submission is still recorded"


@pytest.mark.critical
async def test_bad_key_is_404_not_401(client):
    """404, never 401 — must not reveal whether a key exists."""
    resp = await client.post(
        "/api/forms/webhook/totally-made-up-key", json={"email": "x@y.com"}
    )
    assert resp.status_code == 404


@pytest.mark.high
async def test_inactive_form_rejects_webhook(client, db, admin_user: User):
    form = await _make_form(db, admin_user, active=False)
    form.webhook_key = "inactive-key"
    await db.commit()

    resp = await client.post(
        "/api/forms/webhook/inactive-key", json={"email": "x@y.com"}
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_webhook_fires_form_submitted_automation(client, db, admin_user: User):
    """The point of 'brings everything into the CRM': a lead can trigger a
    workflow (auto-reply, tag, etc.)."""
    from app.workflows.models import (
        ActionType,
        ExecutionStatus,
        TriggerType,
        Workflow,
        WorkflowExecution,
        WorkflowStep,
    )

    form = await _make_form(db, admin_user)
    form.webhook_key = "automation-key"
    await db.commit()

    # An active FORM_SUBMITTED workflow that tags the new contact.
    wf = Workflow(
        id=uuid.uuid4(),
        name="Tag new web leads",
        trigger_type=TriggerType.FORM_SUBMITTED,
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(wf)
    await db.flush()
    db.add(
        WorkflowStep(
            id=uuid.uuid4(),
            workflow_id=wf.id,
            step_order=1,
            action_type=ActionType.ADD_TAG,
            action_config_json=json.dumps({"tag_name": "web-lead"}),
        )
    )
    await db.commit()

    resp = await client.post(
        "/api/forms/webhook/automation-key",
        json={"email": "auto@lead.com", "name": "Auto Lead"},
    )
    assert resp.status_code == 201

    # The workflow ran.
    execs = (
        await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == wf.id)
        )
    ).scalars().all()
    assert len(execs) == 1
    assert execs[0].status == ExecutionStatus.COMPLETED

    # ...and actually tagged the contact.
    from app.contacts.models import ContactTag

    contact = (
        await db.execute(select(Contact).where(Contact.email == "auto@lead.com"))
    ).scalar_one()
    tags = (
        await db.execute(select(ContactTag).where(ContactTag.contact_id == contact.id))
    ).scalars().all()
    assert any(t.tag_name == "web-lead" for t in tags)


@pytest.mark.high
async def test_a_lead_with_no_email_is_still_recorded(client, db, admin_user: User):
    """Some site forms omit email (phone-only). Store the submission anyway —
    losing a lead is worse than a contact with no email."""
    form = await _make_form(db, admin_user)
    form.webhook_key = "no-email-key"
    await db.commit()

    resp = await client.post(
        "/api/forms/webhook/no-email-key",
        json={"name": "Phone Only", "phone": "+15559999999"},
    )
    assert resp.status_code == 201

    subs = (
        await db.execute(select(FormSubmission).where(FormSubmission.form_id == form.id))
    ).scalars().all()
    assert len(subs) == 1
    assert subs[0].contact_id is None  # no email → no contact match/create
