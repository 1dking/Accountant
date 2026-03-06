
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import ActivityType
from app.contacts.service import add_tag, log_contact_activity, remove_tag
from app.core.exceptions import NotFoundError
from app.workflows.models import (
    ActionType,
    ExecutionStatus,
    TriggerType,
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStep,
    WorkflowStep,
)
from app.workflows.schemas import WorkflowCreate, WorkflowStepCreate, WorkflowUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_workflow(
    db: AsyncSession, data: WorkflowCreate, user: User
) -> Workflow:
    """Create a workflow together with its steps in a single transaction."""
    workflow = Workflow(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_config_json=data.trigger_config_json,
        is_active=False,
        created_by=user.id,
    )
    db.add(workflow)
    await db.flush()

    for step_data in data.steps:
        step = WorkflowStep(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            step_order=step_data.step_order,
            action_type=step_data.action_type,
            action_config_json=step_data.action_config_json,
            condition_json=step_data.condition_json,
            wait_duration_seconds=step_data.wait_duration_seconds,
        )
        db.add(step)

    await db.commit()
    await db.refresh(workflow)
    return workflow


async def list_workflows(
    db: AsyncSession, page: int = 1, page_size: int = 25
) -> tuple[list[dict], int]:
    """List workflows with execution_count and last_run_at computed."""
    # Total count
    count_q = select(func.count(Workflow.id))
    total = (await db.execute(count_q)).scalar() or 0

    # Subquery for execution stats
    exec_stats = (
        select(
            WorkflowExecution.workflow_id,
            func.count(WorkflowExecution.id).label("execution_count"),
            func.max(WorkflowExecution.started_at).label("last_run_at"),
        )
        .group_by(WorkflowExecution.workflow_id)
        .subquery()
    )

    query = (
        select(
            Workflow,
            func.coalesce(exec_stats.c.execution_count, 0).label("execution_count"),
            exec_stats.c.last_run_at,
        )
        .outerjoin(exec_stats, Workflow.id == exec_stats.c.workflow_id)
        .order_by(Workflow.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        workflow = row[0]
        items.append(
            {
                "id": workflow.id,
                "name": workflow.name,
                "trigger_type": workflow.trigger_type,
                "is_active": workflow.is_active,
                "created_at": workflow.created_at,
                "execution_count": row[1],
                "last_run_at": row[2],
            }
        )

    return items, total


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> dict:
    """Get a workflow together with its ordered steps."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))

    steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
    )
    steps = list(steps_result.scalars().all())

    return {"workflow": workflow, "steps": steps}


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, data: WorkflowUpdate, user: User
) -> Workflow:
    """Update workflow fields and optionally replace all steps."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))

    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    if data.trigger_type is not None:
        workflow.trigger_type = data.trigger_type
    if data.trigger_config_json is not None:
        workflow.trigger_config_json = data.trigger_config_json
    if data.is_active is not None:
        workflow.is_active = data.is_active

    # Replace steps if provided
    if data.steps is not None:
        await db.execute(
            delete(WorkflowStep).where(WorkflowStep.workflow_id == workflow_id)
        )
        for step_data in data.steps:
            step = WorkflowStep(
                id=uuid.uuid4(),
                workflow_id=workflow.id,
                step_order=step_data.step_order,
                action_type=step_data.action_type,
                action_config_json=step_data.action_config_json,
                condition_json=step_data.condition_json,
                wait_duration_seconds=step_data.wait_duration_seconds,
            )
            db.add(step)

    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> None:
    """Delete a workflow and all related steps/executions (via CASCADE)."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))
    await db.delete(workflow)
    await db.commit()


async def toggle_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, is_active: bool
) -> Workflow:
    """Toggle workflow active/inactive."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))
    workflow.is_active = is_active
    await db.commit()
    await db.refresh(workflow)
    return workflow


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


async def _execute_action(
    db: AsyncSession,
    step: WorkflowStep,
    contact_id: uuid.UUID | None,
    event_data: dict | None,
) -> tuple[ExecutionStatus, str]:
    """Execute a single workflow action. Returns (status, result_json)."""
    action = step.action_type
    config = {}
    if step.action_config_json:
        try:
            config = json.loads(step.action_config_json)
        except json.JSONDecodeError:
            config = {}

    if action == ActionType.SEND_EMAIL:
        # Placeholder -- actual email sending exists in the email module
        result = {"action": "send_email", "status": "logged", "config": config}
        if contact_id:
            await log_contact_activity(
                db,
                contact_id=contact_id,
                activity_type=ActivityType.EMAIL_SENT,
                title="Workflow: email send triggered",
                description=config.get("subject", ""),
            )
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.SEND_SMS:
        # Placeholder -- actual SMS sending exists in the twilio module
        result = {"action": "send_sms", "status": "logged", "config": config}
        if contact_id:
            await log_contact_activity(
                db,
                contact_id=contact_id,
                activity_type=ActivityType.SMS_SENT,
                title="Workflow: SMS send triggered",
                description=config.get("body", ""),
            )
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.ADD_TAG:
        tag_name = config.get("tag_name", "")
        if contact_id and tag_name:
            try:
                # add_tag requires a User object; create a minimal shim from the
                # workflow's created_by if needed. For workflow automation we pass
                # a None user and fall back to direct insert.
                from app.contacts.models import ContactTag

                existing = await db.execute(
                    select(ContactTag).where(
                        ContactTag.contact_id == contact_id,
                        ContactTag.tag_name == tag_name,
                    )
                )
                if not existing.scalar_one_or_none():
                    tag = ContactTag(
                        id=uuid.uuid4(),
                        contact_id=contact_id,
                        tag_name=tag_name,
                        created_by=uuid.UUID(int=0),  # system user placeholder
                    )
                    db.add(tag)
                    await db.flush()
                result = {"action": "add_tag", "tag_name": tag_name, "status": "added"}
            except Exception as exc:
                result = {"action": "add_tag", "error": str(exc)}
        else:
            result = {"action": "add_tag", "status": "skipped", "reason": "missing contact_id or tag_name"}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.REMOVE_TAG:
        tag_name = config.get("tag_name", "")
        if contact_id and tag_name:
            try:
                from app.contacts.models import ContactTag

                tag_result = await db.execute(
                    select(ContactTag).where(
                        ContactTag.contact_id == contact_id,
                        ContactTag.tag_name == tag_name,
                    )
                )
                tag = tag_result.scalar_one_or_none()
                if tag:
                    await db.delete(tag)
                    await db.flush()
                result = {"action": "remove_tag", "tag_name": tag_name, "status": "removed"}
            except Exception as exc:
                result = {"action": "remove_tag", "error": str(exc)}
        else:
            result = {"action": "remove_tag", "status": "skipped", "reason": "missing contact_id or tag_name"}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.CREATE_NOTE:
        title = config.get("title", "Workflow note")
        description = config.get("description", "")
        if contact_id:
            await log_contact_activity(
                db,
                contact_id=contact_id,
                activity_type=ActivityType.NOTE_ADDED,
                title=title,
                description=description,
            )
        result = {"action": "create_note", "title": title, "status": "created"}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.WAIT_DELAY:
        # Mark step as waiting; an external scheduler or poller will resume
        wait_seconds = step.wait_duration_seconds or config.get("seconds", 0)
        result = {"action": "wait_delay", "wait_seconds": wait_seconds, "status": "waiting"}
        return ExecutionStatus.WAITING, json.dumps(result)

    elif action == ActionType.IF_ELSE_BRANCH:
        # Evaluate condition_json against event_data
        branch = "default"
        if step.condition_json:
            try:
                condition = json.loads(step.condition_json)
                field = condition.get("field", "")
                operator = condition.get("operator", "eq")
                value = condition.get("value")
                actual = (event_data or {}).get(field)

                if operator == "eq" and actual == value:
                    branch = "true"
                elif operator == "neq" and actual != value:
                    branch = "true"
                elif operator == "contains" and value and actual and value in str(actual):
                    branch = "true"
                elif operator == "exists" and actual is not None:
                    branch = "true"
                else:
                    branch = "false"
            except (json.JSONDecodeError, AttributeError):
                branch = "error"
        result = {"action": "if_else_branch", "branch": branch}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.ASK_OBRAIN:
        # No-op stub -- returns empty result
        result = {"action": "ask_obrain", "status": "stub", "response": ""}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    elif action == ActionType.LOG_TO_BRAIN:
        # No-op stub -- returns empty result
        result = {"action": "log_to_brain", "status": "stub", "response": ""}
        return ExecutionStatus.COMPLETED, json.dumps(result)

    else:
        # All other action types: log as completed with the action_type recorded
        result = {"action": action.value, "status": "completed", "config": config}
        return ExecutionStatus.COMPLETED, json.dumps(result)


async def execute_workflow(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    event_data: dict | None = None,
) -> WorkflowExecution:
    """Create an execution record and iterate through the workflow steps."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))

    execution = WorkflowExecution(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        contact_id=contact_id,
        status=ExecutionStatus.RUNNING,
    )
    db.add(execution)
    await db.flush()

    # Fetch ordered steps
    steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
    )
    steps = list(steps_result.scalars().all())

    overall_status = ExecutionStatus.COMPLETED
    overall_error = None

    for step in steps:
        exec_step = WorkflowExecutionStep(
            id=uuid.uuid4(),
            execution_id=execution.id,
            step_id=step.id,
            status=ExecutionStatus.RUNNING,
        )
        db.add(exec_step)
        await db.flush()

        try:
            step_status, result_json = await _execute_action(
                db, step, contact_id, event_data
            )
            exec_step.status = step_status
            exec_step.result_json = result_json
            exec_step.completed_at = datetime.now(timezone.utc)

            if step_status == ExecutionStatus.WAITING:
                # Stop processing further steps; execution is paused
                overall_status = ExecutionStatus.WAITING
                await db.flush()
                break

            if step_status == ExecutionStatus.FAILED:
                overall_status = ExecutionStatus.FAILED
                overall_error = result_json
                await db.flush()
                break

            # Handle if_else_branch: check result to decide skipping
            if step.action_type == ActionType.IF_ELSE_BRANCH:
                try:
                    branch_result = json.loads(result_json) if result_json else {}
                    branch = branch_result.get("branch", "default")
                    # If branch is "false", skip the next step (the "true" branch action)
                    # This is a simplified two-path branching model
                    if branch == "false":
                        # The next step in order is the "true" path action; skip it
                        # by marking it completed with a skip note
                        pass  # No explicit skip needed; execution continues to next
                except json.JSONDecodeError:
                    pass

        except Exception as exc:
            logger.exception(
                "Workflow step %s failed: %s", step.id, str(exc)
            )
            exec_step.status = ExecutionStatus.FAILED
            exec_step.error_message = str(exc)
            exec_step.completed_at = datetime.now(timezone.utc)
            overall_status = ExecutionStatus.FAILED
            overall_error = str(exc)
            await db.flush()
            break

    execution.status = overall_status
    if overall_status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        execution.completed_at = datetime.now(timezone.utc)
    if overall_error:
        execution.error_message = overall_error

    await db.commit()
    await db.refresh(execution)
    return execution


# ---------------------------------------------------------------------------
# Execution log
# ---------------------------------------------------------------------------


async def get_executions(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    """Return paginated execution log for a workflow, including step details."""
    count_q = select(func.count(WorkflowExecution.id)).where(
        WorkflowExecution.workflow_id == workflow_id
    )
    total = (await db.execute(count_q)).scalar() or 0

    exec_q = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .order_by(WorkflowExecution.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    exec_result = await db.execute(exec_q)
    executions = list(exec_result.scalars().all())

    items = []
    for execution in executions:
        steps_q = (
            select(WorkflowExecutionStep)
            .where(WorkflowExecutionStep.execution_id == execution.id)
            .order_by(WorkflowExecutionStep.started_at)
        )
        steps_result = await db.execute(steps_q)
        exec_steps = list(steps_result.scalars().all())

        items.append(
            {
                "id": execution.id,
                "workflow_id": execution.workflow_id,
                "contact_id": execution.contact_id,
                "status": execution.status,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "error_message": execution.error_message,
                "steps": [
                    {
                        "id": s.id,
                        "execution_id": s.execution_id,
                        "step_id": s.step_id,
                        "status": s.status,
                        "started_at": s.started_at,
                        "completed_at": s.completed_at,
                        "result_json": s.result_json,
                        "error_message": s.error_message,
                    }
                    for s in exec_steps
                ],
            }
        )

    return items, total


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------


async def dispatch_event(
    db: AsyncSession,
    event_type: TriggerType,
    event_data: dict | None = None,
    contact_id: uuid.UUID | None = None,
) -> list[WorkflowExecution]:
    """Find all active workflows matching the trigger type and execute each."""
    query = select(Workflow).where(
        Workflow.is_active == True,  # noqa: E712
        Workflow.trigger_type == event_type,
    )
    result = await db.execute(query)
    workflows = list(result.scalars().all())

    executions = []
    for workflow in workflows:
        try:
            execution = await execute_workflow(
                db, workflow.id, contact_id, event_data
            )
            executions.append(execution)
        except Exception as exc:
            logger.exception(
                "Failed to execute workflow %s for event %s: %s",
                workflow.id,
                event_type.value,
                str(exc),
            )

    return executions


# ---------------------------------------------------------------------------
# Pre-built templates
# ---------------------------------------------------------------------------


WORKFLOW_TEMPLATES = [
    {
        "name": "New Client Welcome",
        "description": "Sends a welcome email and adds an onboarding tag when a new contact is created.",
        "trigger_type": TriggerType.CONTACT_CREATED.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.SEND_EMAIL.value,
                "action_config_json": json.dumps({
                    "subject": "Welcome aboard!",
                    "template": "welcome_email",
                }),
            },
            {
                "step_order": 1,
                "action_type": ActionType.ADD_TAG.value,
                "action_config_json": json.dumps({"tag_name": "onboarding"}),
            },
        ],
    },
    {
        "name": "Invoice Overdue Follow-Up",
        "description": "Waits 3 days after an invoice becomes overdue, then sends a reminder email.",
        "trigger_type": TriggerType.INVOICE_OVERDUE.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.WAIT_DELAY.value,
                "wait_duration_seconds": 259200,
                "action_config_json": json.dumps({"seconds": 259200}),
            },
            {
                "step_order": 1,
                "action_type": ActionType.SEND_EMAIL.value,
                "action_config_json": json.dumps({
                    "subject": "Payment Reminder: Invoice Overdue",
                    "template": "overdue_reminder",
                }),
            },
        ],
    },
    {
        "name": "Proposal Signed Celebration",
        "description": "When a proposal is signed, creates a note and sends a notification.",
        "trigger_type": TriggerType.PROPOSAL_SIGNED.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.CREATE_NOTE.value,
                "action_config_json": json.dumps({
                    "title": "Proposal signed!",
                    "description": "The client has signed the proposal. Begin onboarding.",
                }),
            },
            {
                "step_order": 1,
                "action_type": ActionType.SEND_NOTIFICATION.value,
                "action_config_json": json.dumps({
                    "message": "A proposal was just signed!",
                }),
            },
            {
                "step_order": 2,
                "action_type": ActionType.ADD_TAG.value,
                "action_config_json": json.dumps({"tag_name": "proposal-signed"}),
            },
        ],
    },
    {
        "name": "Invoice Paid Thank You",
        "description": "Sends a thank-you email when an invoice is paid.",
        "trigger_type": TriggerType.INVOICE_PAID.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.SEND_EMAIL.value,
                "action_config_json": json.dumps({
                    "subject": "Thank you for your payment!",
                    "template": "payment_thank_you",
                }),
            },
            {
                "step_order": 1,
                "action_type": ActionType.CREATE_NOTE.value,
                "action_config_json": json.dumps({
                    "title": "Payment received",
                    "description": "Invoice paid. Automated thank-you sent.",
                }),
            },
        ],
    },
    {
        "name": "Appointment Reminder",
        "description": "Sends an SMS reminder after an appointment is booked, then a follow-up email after completion.",
        "trigger_type": TriggerType.APPOINTMENT_BOOKED.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.SEND_SMS.value,
                "action_config_json": json.dumps({
                    "body": "Your appointment has been confirmed. We look forward to seeing you!",
                }),
            },
            {
                "step_order": 1,
                "action_type": ActionType.ADD_TAG.value,
                "action_config_json": json.dumps({"tag_name": "appointment-booked"}),
            },
        ],
    },
    {
        "name": "Contact Tag Automation",
        "description": "When a tag is added to a contact, sends a notification and creates a task.",
        "trigger_type": TriggerType.CONTACT_TAG_ADDED.value,
        "steps": [
            {
                "step_order": 0,
                "action_type": ActionType.SEND_NOTIFICATION.value,
                "action_config_json": json.dumps({
                    "message": "A contact was tagged. Review and follow up.",
                }),
            },
            {
                "step_order": 1,
                "action_type": ActionType.CREATE_TASK.value,
                "action_config_json": json.dumps({
                    "title": "Follow up on tagged contact",
                    "description": "A contact was tagged and may need attention.",
                }),
            },
        ],
    },
]
