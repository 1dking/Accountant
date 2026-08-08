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
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
    WorkflowExecution,
    WorkflowExecutionStep,
    WorkflowStep,
)
from app.workflows.service import execute_workflow, resume_waiting_workflows
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


async def _make_multi(db, owner: User, specs: list[dict]) -> Workflow:
    """Build an active, step-authored workflow from a list of step specs.

    Each spec: {"action_type", "config"?, "condition"?, "wait_seconds"?}.
    Step order follows list order.
    """
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Multi-Step Automation",
        trigger_type=TriggerType.CONTACT_CREATED,
        is_active=True,
        created_by=owner.id,
    )
    db.add(workflow)
    await db.flush()
    for order, spec in enumerate(specs):
        db.add(
            WorkflowStep(
                id=uuid.uuid4(),
                workflow_id=workflow.id,
                step_order=order,
                action_type=spec["action_type"],
                action_config_json=json.dumps(spec.get("config", {})),
                condition_json=json.dumps(spec["condition"]) if spec.get("condition") else None,
                wait_duration_seconds=spec.get("wait_seconds"),
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
async def test_create_contact_action_creates_a_contact(
    db, admin_user: User, sample_contact: Contact
):
    """CREATE_CONTACT must insert a real, owned contact row."""
    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.CREATE_CONTACT,
        {"company_name": "NewCo", "contact_name": "Pat Lee", "email": "pat@newco.com", "type": "client"},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    new_id = uuid.UUID(steps[0]["result"]["contact_id"])
    created = (
        await db.execute(select(Contact).where(Contact.id == new_id))
    ).scalar_one()
    assert created.company_name == "NewCo"
    assert created.email == "pat@newco.com"
    assert created.created_by == admin_user.id, "must be owned by the workflow owner"
    assert execution.status == ExecutionStatus.COMPLETED


@pytest.mark.critical
async def test_create_invoice_action_creates_an_invoice(
    db, admin_user: User, sample_contact: Contact
):
    """CREATE_INVOICE must produce a real invoice for the triggering contact."""
    from app.invoicing.models import Invoice

    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.CREATE_INVOICE,
        {"line_items": [{"description": "Retainer", "quantity": 1, "unit_price": 500}], "due_in_days": 14},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    inv_id = uuid.UUID(steps[0]["result"]["invoice_id"])
    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == inv_id))
    ).scalar_one()
    assert invoice.contact_id == sample_contact.id
    assert invoice.total == Decimal("500.00")


@pytest.mark.critical
async def test_create_invoice_without_contact_fails(db, admin_user: User):
    """No contact + no config contact_id -> a clear failure, not a silent skip."""
    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.CREATE_INVOICE,
        {"line_items": [{"description": "x", "quantity": 1, "unit_price": 10}]},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=None)
    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED
    assert "contact" in steps[0]["result"]["error"].lower()


@pytest.mark.high
async def test_send_proposal_action_sends_a_draft(
    db, admin_user: User, sample_contact: Contact, monkeypatch
):
    """SEND_PROPOSAL must move a DRAFT proposal to SENT via the real service."""
    from app.proposals.models import Proposal, ProposalRecipient, ProposalStatus

    proposal = Proposal(
        id=uuid.uuid4(),
        proposal_number="PROP-9001",
        contact_id=sample_contact.id,
        title="Engagement",
        content_json="{}",
        value=Decimal("1000"),
        currency="USD",
        status=ProposalStatus.DRAFT,
        created_by=admin_user.id,
    )
    db.add(proposal)
    await db.flush()
    db.add(
        ProposalRecipient(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            email="signer@acme.com",
            name="John Doe",
            role="signer",
        )
    )
    await db.commit()

    async def _stub_send_proposal_email(*args, **kwargs):
        return {"sent": ["signer@acme.com"], "failed": []}

    monkeypatch.setattr(
        "app.email.service.send_proposal_email", _stub_send_proposal_email
    )

    workflow = await _make_workflow(
        db, admin_user, ActionType.SEND_PROPOSAL, {"proposal_id": str(proposal.id)}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    assert steps[0]["result"]["status"] == "sent"
    await db.refresh(proposal)
    assert proposal.status == ProposalStatus.SENT


@pytest.mark.high
async def test_move_pipeline_stage_moves_proposal_status(
    db, admin_user: User, sample_contact: Contact
):
    """MOVE_PIPELINE_STAGE == move the associated proposal's status (no deals
    entity yet). 'won' maps to signed."""
    from app.proposals.models import Proposal, ProposalStatus

    proposal = Proposal(
        id=uuid.uuid4(),
        proposal_number="PROP-9101",
        contact_id=sample_contact.id,
        title="Pipeline",
        content_json="{}",
        value=Decimal("1"),
        currency="USD",
        status=ProposalStatus.SENT,
        created_by=admin_user.id,
    )
    db.add(proposal)
    await db.commit()

    workflow = await _make_workflow(
        db, admin_user, ActionType.MOVE_PIPELINE_STAGE, {"stage": "won"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    assert steps[0]["result"]["to"] == "signed"
    await db.refresh(proposal)
    assert proposal.status == ProposalStatus.SIGNED


@pytest.mark.high
async def test_add_to_workflow_enrolls_contact(
    db, admin_user: User, sample_contact: Contact
):
    """ADD_TO_WORKFLOW enrols the contact into another workflow (runs it)."""
    target = await _make_workflow(
        db, admin_user, ActionType.ADD_TAG, {"tag_name": "enrolled"}
    )
    enroller = await _make_workflow(
        db, admin_user, ActionType.ADD_TO_WORKFLOW, {"workflow_id": str(target.id)}
    )
    execution = await execute_workflow(db, enroller.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps

    tag = (
        await db.execute(
            select(ContactTag).where(
                ContactTag.contact_id == sample_contact.id,
                ContactTag.tag_name == "enrolled",
            )
        )
    ).scalar_one_or_none()
    assert tag is not None, "the enrolled workflow must have actually run"

    target_execs = (
        await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == target.id)
        )
    ).scalars().all()
    assert len(target_execs) == 1


@pytest.mark.high
async def test_remove_from_workflow_cancels_active_execution(
    db, admin_user: User, sample_contact: Contact
):
    """REMOVE_FROM_WORKFLOW cancels the contact's active enrollment."""
    target = await _make_workflow(db, admin_user, ActionType.ADD_TAG, {"tag_name": "x"})
    enrollment = WorkflowExecution(
        id=uuid.uuid4(),
        workflow_id=target.id,
        contact_id=sample_contact.id,
        status=ExecutionStatus.WAITING,
    )
    db.add(enrollment)
    await db.commit()

    remover = await _make_workflow(
        db, admin_user, ActionType.REMOVE_FROM_WORKFLOW, {"workflow_id": str(target.id)}
    )
    execution = await execute_workflow(db, remover.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    assert steps[0]["result"]["cancelled"] == 1
    await db.refresh(enrollment)
    assert enrollment.status == ExecutionStatus.CANCELLED


@pytest.mark.critical
async def test_ask_obrain_action_meters_and_answers(
    db, admin_user: User, sample_contact: Contact, monkeypatch
):
    """ASK_OBRAIN makes a (mocked) non-streaming Claude call and records it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _Block:
        type = "text"
        text = "Here is the answer."

    class _Resp:
        content = [_Block()]

    class _Msgs:
        async def create(self, **kwargs):
            return _Resp()

    class _Client:
        def __init__(self, **kwargs):
            self.messages = _Msgs()

    monkeypatch.setattr("anthropic.AsyncAnthropic", _Client)

    sample_contact.contact_name = "Dana"
    await db.commit()

    workflow = await _make_workflow(
        db, admin_user, ActionType.ASK_OBRAIN, {"prompt": "Summarize {contact_name}"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    assert steps[0]["result"]["answer"] == "Here is the answer."

    from app.brain.models import BrainAuditLog

    audits = (await db.execute(select(BrainAuditLog))).scalars().all()
    assert any(a.ai_output == "Here is the answer." for a in audits), (
        "the AI interaction must be auditable"
    )


@pytest.mark.critical
async def test_ask_obrain_fails_closed_without_credits(
    db, admin_user: User, sample_contact: Contact, monkeypatch
):
    """No credits => the step FAILS and the model is never called (fail-closed)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from app.billing.ai_meter import AiCreditsExhausted

    async def _no_credits(*args, **kwargs):
        raise AiCreditsExhausted(
            "out of credits", used=999, limit=1000, operation="workflow_ask_obrain"
        )

    monkeypatch.setattr("app.billing.ai_meter.consume", _no_credits)

    called: list = []

    class _Client:
        def __init__(self, **kwargs):
            called.append(1)

    monkeypatch.setattr("anthropic.AsyncAnthropic", _Client)

    workflow = await _make_workflow(
        db, admin_user, ActionType.ASK_OBRAIN, {"prompt": "hi"}
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.FAILED
    assert steps[0]["result"]["code"] == "ai_credits_exhausted"
    assert called == [], "must not call the model when out of credits"


@pytest.mark.high
async def test_log_to_brain_action_stores_embedding(
    db, admin_user: User, sample_contact: Contact
):
    """LOG_TO_BRAIN writes searchable knowledge into brain_embeddings."""
    from app.brain.models import BrainEmbedding

    workflow = await _make_workflow(
        db,
        admin_user,
        ActionType.LOG_TO_BRAIN,
        {"content": "Client prefers email over phone."},
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    steps = await _step_results(db, execution.id)
    assert steps[0]["status"] == ExecutionStatus.COMPLETED, steps
    assert steps[0]["result"]["chunks_stored"] >= 1

    embeddings = (
        await db.execute(
            select(BrainEmbedding).where(BrainEmbedding.contact_id == sample_contact.id)
        )
    ).scalars().all()
    assert len(embeddings) >= 1
    assert embeddings[0].user_id == admin_user.id


# ---------------------------------------------------------------------------
# WAIT_DELAY resumption
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_wait_delay_parks_then_resumes(
    db, admin_user: User, sample_contact: Contact
):
    """A WAIT_DELAY must park the run and later be resumed to completion — the
    whole point being that the step AFTER the delay eventually runs."""
    workflow = await _make_multi(
        db,
        admin_user,
        [
            {"action_type": ActionType.WAIT_DELAY, "wait_seconds": 3600},
            {"action_type": ActionType.ADD_TAG, "config": {"tag_name": "after-wait"}},
        ],
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    # Parked, with everything the poller needs to continue.
    assert execution.status == ExecutionStatus.WAITING
    assert execution.resume_step_index == 1
    assert execution.resume_at is not None

    async def _has_tag() -> bool:
        row = (
            await db.execute(
                select(ContactTag).where(
                    ContactTag.contact_id == sample_contact.id,
                    ContactTag.tag_name == "after-wait",
                )
            )
        ).scalar_one_or_none()
        return row is not None

    assert not await _has_tag(), "the post-delay step must not have run yet"

    # Not due yet -> the poller leaves it alone.
    assert await resume_waiting_workflows(db, now=datetime.now(timezone.utc)) == 0
    await db.refresh(execution)
    assert execution.status == ExecutionStatus.WAITING

    # Once the delay has elapsed -> resumed to completion, post-delay step runs.
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert await resume_waiting_workflows(db, now=future) == 1
    await db.refresh(execution)
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.completed_at is not None
    assert await _has_tag(), "the post-delay step must run after resume"


@pytest.mark.high
async def test_wait_delay_chained_delays_repark(
    db, admin_user: User, sample_contact: Contact
):
    """Two delays in a row: resuming the first must honour the second (re-park),
    then a later resume finishes the run."""
    workflow = await _make_multi(
        db,
        admin_user,
        [
            {"action_type": ActionType.WAIT_DELAY, "wait_seconds": 60},
            {"action_type": ActionType.ADD_TAG, "config": {"tag_name": "mid"}},
            {"action_type": ActionType.WAIT_DELAY, "wait_seconds": 60},
            {"action_type": ActionType.CREATE_NOTE, "config": {"title": "done"}},
        ],
    )
    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)
    assert execution.status == ExecutionStatus.WAITING
    assert execution.resume_step_index == 1

    # First resume runs ADD_TAG then hits the second delay -> re-parks at step 3.
    t1 = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert await resume_waiting_workflows(db, now=t1) == 1
    await db.refresh(execution)
    assert execution.status == ExecutionStatus.WAITING
    assert execution.resume_step_index == 3

    # Second resume runs the final CREATE_NOTE -> complete.
    t2 = datetime.now(timezone.utc) + timedelta(minutes=4)
    assert await resume_waiting_workflows(db, now=t2) == 1
    await db.refresh(execution)
    assert execution.status == ExecutionStatus.COMPLETED

    notes = (
        await db.execute(
            select(ContactActivity).where(
                ContactActivity.contact_id == sample_contact.id,
                ContactActivity.activity_type == ActivityType.NOTE_ADDED,
                ContactActivity.title == "done",
            )
        )
    ).scalars().all()
    assert len(notes) == 1


# ---------------------------------------------------------------------------
# Linear IF_ELSE_BRANCH routing
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_if_else_branch_false_skips_next_step(
    db, admin_user: User, sample_contact: Contact
):
    """When the condition is false, the immediately-following (true-branch)
    step is skipped; the step after it still runs."""
    workflow = await _make_multi(
        db,
        admin_user,
        [
            {
                "action_type": ActionType.IF_ELSE_BRANCH,
                "condition": {"field": "score", "operator": "eq", "value": "high"},
            },
            {"action_type": ActionType.ADD_TAG, "config": {"tag_name": "vip"}},
            {"action_type": ActionType.CREATE_NOTE, "config": {"title": "reached"}},
        ],
    )
    execution = await execute_workflow(
        db, workflow.id, contact_id=sample_contact.id, event_data={"score": "low"}
    )
    assert execution.status == ExecutionStatus.COMPLETED

    vip = (
        await db.execute(
            select(ContactTag).where(
                ContactTag.contact_id == sample_contact.id,
                ContactTag.tag_name == "vip",
            )
        )
    ).scalar_one_or_none()
    assert vip is None, "the true-branch step must be skipped when condition is false"

    steps = await _step_results(db, execution.id)
    assert any(s["result"].get("status") == "skipped" for s in steps), (
        "the skip must be recorded in the execution log"
    )

    reached = (
        await db.execute(
            select(ContactActivity).where(
                ContactActivity.contact_id == sample_contact.id,
                ContactActivity.activity_type == ActivityType.NOTE_ADDED,
                ContactActivity.title == "reached",
            )
        )
    ).scalars().all()
    assert len(reached) == 1, "the step after the skipped one must still run"


@pytest.mark.high
async def test_if_else_branch_true_runs_next_step(
    db, admin_user: User, sample_contact: Contact
):
    """When the condition is true, the following step runs normally."""
    workflow = await _make_multi(
        db,
        admin_user,
        [
            {
                "action_type": ActionType.IF_ELSE_BRANCH,
                "condition": {"field": "score", "operator": "eq", "value": "high"},
            },
            {"action_type": ActionType.ADD_TAG, "config": {"tag_name": "vip"}},
        ],
    )
    execution = await execute_workflow(
        db, workflow.id, contact_id=sample_contact.id, event_data={"score": "high"}
    )
    assert execution.status == ExecutionStatus.COMPLETED

    vip = (
        await db.execute(
            select(ContactTag).where(
                ContactTag.contact_id == sample_contact.id,
                ContactTag.tag_name == "vip",
            )
        )
    ).scalar_one_or_none()
    assert vip is not None, "the true-branch step must run when condition is true"


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
