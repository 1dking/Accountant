"""Workflow actions must do what they claim.

The engine used to return COMPLETED for SEND_EMAIL/SEND_SMS while sending
nothing — and then write an EMAIL_SENT/SMS_SENT row to the contact timeline.
That corrupts the audit trail: the UI showed "we emailed them" for mail that
never left. Eleven more action types fell through a catch-all `else` that
reported success for doing nothing at all.

These tests assert on the *effect* of an action, never just its status, which
is the only thing that would have caught the original bug.
"""
import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth.models import User
from app.contacts.models import ActivityType, Contact, ContactActivity, ContactTag
from app.core.encryption import init_encryption_service
from app.workflows.models import (
    ActionType,
    ExecutionStatus,
    TriggerType,
    Workflow,
    WorkflowExecutionStep,
    WorkflowStep,
)
from app.workflows.service import execute_workflow
from tests.conftest import TEST_SETTINGS

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
    from app.core.encryption import get_encryption_service
    from app.email.models import SmtpConfig

    cfg = SmtpConfig(
        id=uuid.uuid4(),
        name="Default",
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        encrypted_password=get_encryption_service().encrypt("dummy"),
        from_email="noreply@example.com",
        from_name="Accountant Test",
        use_tls=True,
        is_default=True,
        created_by=admin_user.id,
    )
    db.add(cfg)
    await db.commit()
    return cfg


async def _make_workflow(
    db, owner: User, action_type: ActionType, config: dict
) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Test Automation",
        trigger_type=TriggerType.CONTACT_CREATED,
        is_active=True,
        created_by=owner.id,
    )
    db.add(workflow)
    await db.flush()
    db.add(
        WorkflowStep(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            step_order=1,
            action_type=action_type,
            action_config_json=json.dumps(config),
        )
    )
    await db.commit()
    return workflow


async def _step_results(db, execution_id) -> list[dict]:
    rows = (
        await db.execute(
            select(WorkflowExecutionStep).where(
                WorkflowExecutionStep.execution_id == execution_id
            )
        )
    ).scalars().all()
    return [
        {"status": r.status, "result": json.loads(r.result_json or "{}")} for r in rows
    ]


async def _activities(db, contact_id, activity_type) -> list[ContactActivity]:
    rows = (
        await db.execute(
            select(ContactActivity).where(
                ContactActivity.contact_id == contact_id,
                ContactActivity.activity_type == activity_type,
            )
        )
    ).scalars().all()
    return list(rows)


@pytest.mark.critical
async def test_send_email_action_actually_sends(
    db, admin_user: User, sample_contact: Contact, smtp_default, monkeypatch
):
    """SEND_EMAIL must put a real message on the wire."""
    sent: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sent.append({"to": to, "subject": subject, "body": html_body})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    sample_contact.email = "buyer@test.com"
    sample_contact.contact_name = "Dana"
    await db.commit()

    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.SEND_EMAIL,
        {"subject": "Hello {contact_name}", "body": "Hi {contact_name}, welcome."},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    assert len(sent) == 1, "the email must actually be dispatched"
    assert sent[0]["to"] == "buyer@test.com"
    assert sent[0]["subject"] == "Hello Dana", "placeholders must be substituted"

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED
    assert len(await _activities(db, sample_contact.id, ActivityType.EMAIL_SENT)) == 1


@pytest.mark.critical
async def test_send_email_failure_does_not_forge_activity(
    db, admin_user: User, sample_contact: Contact, smtp_default, monkeypatch
):
    """If the send fails, the step must be FAILED and — crucially — no
    EMAIL_SENT row may be written. Forging the timeline was the original bug."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("smtp refused")

    monkeypatch.setattr("app.email.service.send_email", _boom)

    sample_contact.email = "buyer@test.com"
    await db.commit()

    workflow = await _make_workflow(
        db, admin_user, ActionType.SEND_EMAIL, {"subject": "Hi", "body": "there"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED
    assert "smtp refused" in steps[0]["result"]["error"]

    assert await _activities(db, sample_contact.id, ActivityType.EMAIL_SENT) == [], (
        "a failed send must not leave an EMAIL_SENT row on the timeline"
    )


@pytest.mark.critical
async def test_send_email_without_address_fails(
    db, admin_user: User, sample_contact: Contact, smtp_default, monkeypatch
):
    """A contact with no email can't be emailed — say so, don't claim success."""
    sent: list = []

    async def _stub_send(*args, **kwargs):
        sent.append(1)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    sample_contact.email = None
    await db.commit()

    workflow = await _make_workflow(
        db, admin_user, ActionType.SEND_EMAIL, {"subject": "Hi", "body": "there"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED
    assert sent == []
    assert await _activities(db, sample_contact.id, ActivityType.EMAIL_SENT) == []


@pytest.mark.high
async def test_send_email_respects_dnd(
    db, admin_user: User, sample_contact: Contact, smtp_default, monkeypatch
):
    """Do-not-disturb must stop automated mail — it's a compliance setting, and
    an automation is exactly the thing that would otherwise ignore it."""
    sent: list = []

    async def _stub_send(*args, **kwargs):
        sent.append(1)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    sample_contact.email = "buyer@test.com"
    sample_contact.dnd_enabled = True
    await db.commit()

    workflow = await _make_workflow(
        db, admin_user, ActionType.SEND_EMAIL, {"subject": "Hi", "body": "there"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    assert sent == [], "must not email a DND contact"
    steps = await _step_results(db, execution.id)
    assert steps[0]["result"]["status"] == "skipped"
    assert await _activities(db, sample_contact.id, ActivityType.EMAIL_SENT) == []


@pytest.mark.high
async def test_add_tag_attributes_to_workflow_owner(
    db, admin_user: User, sample_contact: Contact
):
    """ADD_TAG used a nil UUID for created_by, which violates the users FK."""
    workflow = await _make_workflow(
        db, admin_user, ActionType.ADD_TAG, {"tag_name": "hot-lead"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED

    tag = (
        await db.execute(
            select(ContactTag).where(
                ContactTag.contact_id == sample_contact.id,
                ContactTag.tag_name == "hot-lead",
            )
        )
    ).scalar_one()
    assert tag.created_by == admin_user.id, "must attribute to a real user"


@pytest.mark.critical
@pytest.mark.parametrize(
    "action_type",
    [
        ActionType.CREATE_CONTACT,
        ActionType.CREATE_INVOICE,
        ActionType.SEND_PROPOSAL,
        ActionType.MOVE_PIPELINE_STAGE,
        ActionType.ADD_TO_WORKFLOW,
        ActionType.REMOVE_FROM_WORKFLOW,
        ActionType.ASK_OBRAIN,
        ActionType.LOG_TO_BRAIN,
    ],
)
async def test_unimplemented_actions_fail_loudly(
    db, admin_user: User, sample_contact: Contact, action_type: ActionType
):
    """These fell through a catch-all that reported COMPLETED for doing nothing.
    Until they're built they must fail, so a workflow that depends on one is
    visibly broken rather than quietly inert."""
    workflow = await _make_workflow(db, admin_user, action_type, {})
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED, (
        f"{action_type.value} must not report success while doing nothing"
    )
    assert "not implemented" in steps[0]["result"]["error"]
    assert execution.status == ExecutionStatus.FAILED


@pytest.mark.high
async def test_webhook_outbound_rejects_plaintext_url(
    db, admin_user: User, sample_contact: Contact
):
    """Webhook payloads carry contact PII and the URL is admin free-text."""
    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.WEBHOOK_OUTBOUND,
        {"url": "http://insecure.example.com/hook"},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED
    assert "https" in steps[0]["result"]["error"]
