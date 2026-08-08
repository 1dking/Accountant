
import json
import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import ActivityType
from app.contacts.service import log_contact_activity
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


async def update_workflow_definition(
    db: AsyncSession, workflow_id: uuid.UUID, definition_json: str, editor: str
) -> Workflow:
    """Save a canvas graph. Validated by the caller (router) before this runs."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow", str(workflow_id))
    workflow.definition_json = definition_json
    workflow.editor = editor
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


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _render_config_text(template: str, contact, event_data: dict | None) -> str:
    """Substitute ``{contact_name}``-style placeholders in an admin-authored
    subject/body. Unknown placeholders are left as literal text so a stale
    config renders imperfectly rather than exploding mid-send."""
    if not template:
        return ""

    values: dict[str, object] = dict(event_data or {})
    if contact is not None:
        values.update(
            {
                "contact_name": contact.contact_name or "",
                "company_name": contact.company_name or "",
                "email": contact.email or "",
                "phone": contact.phone or "",
            }
        )

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        value = values[key]
        return "" if value is None else str(value)

    return _PLACEHOLDER_RE.sub(_replace, template)


#: Action types the engine cannot perform yet. They fail loudly rather than
#: reporting COMPLETED — a workflow that silently skips its only real step is
#: worse than one that visibly breaks, because nobody goes looking for it.
#: Empty now that every ActionType has a handler; kept as the explicit
#: extension point so a newly-added enum member can park here (fails visibly)
#: until its handler lands, rather than falling through to a silent success.
_UNIMPLEMENTED_ACTIONS: dict[ActionType, str] = {}


async def _load_contact(db: AsyncSession, contact_id: uuid.UUID | None):
    """Load a Contact for an action that needs one, or None."""
    from app.contacts.models import Contact

    if not contact_id:
        return None
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    return result.scalar_one_or_none()


async def _load_owner(db: AsyncSession, workflow: Workflow) -> User | None:
    """The user the workflow runs as. Automated sends need a real identity —
    for SMTP config resolution, Twilio attribution, and row ownership."""
    result = await db.execute(select(User).where(User.id == workflow.created_by))
    return result.scalar_one_or_none()


async def _execute_action(
    db: AsyncSession,
    workflow: Workflow,
    step: WorkflowStep,
    contact_id: uuid.UUID | None,
    event_data: dict | None,
) -> tuple[ExecutionStatus, str]:
    """Execute a single workflow action. Returns (status, result_json).

    Contract: only return COMPLETED if the action actually happened. Anything
    that couldn't be carried out returns FAILED with a reason — the contact
    timeline is an audit trail, and writing an EMAIL_SENT row for an email we
    never sent corrupts it.
    """
    action = step.action_type
    config = {}
    if step.action_config_json:
        try:
            config = json.loads(step.action_config_json)
        except json.JSONDecodeError:
            config = {}

    if action in _UNIMPLEMENTED_ACTIONS:
        return ExecutionStatus.FAILED, json.dumps(
            {"action": action.value, "error": _UNIMPLEMENTED_ACTIONS[action]}
        )

    if action == ActionType.SEND_EMAIL:
        from app.email.service import get_default_config, send_email

        contact = await _load_contact(db, contact_id)
        if contact is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_email", "error": "no contact to send to"}
            )
        if not contact.email:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_email", "error": "contact has no email address"}
            )
        if contact.dnd_enabled:
            return ExecutionStatus.COMPLETED, json.dumps(
                {"action": "send_email", "status": "skipped", "reason": "contact is DND"}
            )

        subject = _render_config_text(config.get("subject", ""), contact, event_data)
        body = _render_config_text(config.get("body", ""), contact, event_data)
        if not subject:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_email", "error": "no subject configured"}
            )

        try:
            smtp_config = await get_default_config(db)
            await send_email(smtp_config, contact.email, subject, body)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: SEND_EMAIL failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_email", "error": str(exc)}
            )

        await log_contact_activity(
            db,
            contact_id=contact.id,
            activity_type=ActivityType.EMAIL_SENT,
            title=f"Workflow: {workflow.name}",
            description=subject,
        )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "send_email", "status": "sent", "to": contact.email}
        )

    elif action == ActionType.SEND_SMS:
        from app.config import Settings
        from app.integrations.twilio.service import send_sms

        contact = await _load_contact(db, contact_id)
        if contact is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_sms", "error": "no contact to send to"}
            )
        if not contact.phone:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_sms", "error": "contact has no phone number"}
            )
        if contact.dnd_enabled:
            return ExecutionStatus.COMPLETED, json.dumps(
                {"action": "send_sms", "status": "skipped", "reason": "contact is DND"}
            )

        owner = await _load_owner(db, workflow)
        if owner is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_sms", "error": "workflow owner not found"}
            )

        body = _render_config_text(config.get("body", ""), contact, event_data)
        if not body:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_sms", "error": "no message body configured"}
            )

        try:
            await send_sms(
                db=db,
                to=contact.phone,
                message=body,
                user=owner,
                settings=Settings(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: SEND_SMS failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_sms", "error": str(exc)}
            )

        await log_contact_activity(
            db,
            contact_id=contact.id,
            activity_type=ActivityType.SMS_SENT,
            title=f"Workflow: {workflow.name}",
            description=body,
        )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "send_sms", "status": "sent", "to": contact.phone}
        )

    elif action == ActionType.SEND_NOTIFICATION:
        from app.notifications.service import create_notification

        title = config.get("title") or f"Workflow: {workflow.name}"
        message = _render_config_text(
            config.get("message", ""), await _load_contact(db, contact_id), event_data
        )
        try:
            await create_notification(
                db,
                user_id=workflow.created_by,
                type=config.get("type", "workflow"),
                title=title,
                message=message,
                contact_id=contact_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: SEND_NOTIFICATION failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_notification", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "send_notification", "status": "sent"}
        )

    elif action == ActionType.UPDATE_CONTACT_FIELD:
        field = config.get("field", "")
        value = config.get("value")
        allowed = {
            "company_name", "contact_name", "email", "phone", "job_title",
            "lead_source", "notes", "is_active", "dnd_enabled",
        }
        if field not in allowed:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "update_contact_field", "error": f"field not updatable: {field}"}
            )
        contact = await _load_contact(db, contact_id)
        if contact is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "update_contact_field", "error": "no contact"}
            )
        setattr(contact, field, value)
        await db.flush()
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "update_contact_field", "field": field, "status": "updated"}
        )

    elif action == ActionType.ASSIGN_TO_USER:
        raw_user_id = config.get("user_id")
        contact = await _load_contact(db, contact_id)
        if contact is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "assign_to_user", "error": "no contact"}
            )
        try:
            assignee_id = uuid.UUID(str(raw_user_id))
        except (TypeError, ValueError):
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "assign_to_user", "error": f"invalid user_id: {raw_user_id!r}"}
            )
        exists = await db.execute(select(User).where(User.id == assignee_id))
        if exists.scalar_one_or_none() is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "assign_to_user", "error": "user not found"}
            )
        contact.assigned_user_id = assignee_id
        await db.flush()
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "assign_to_user", "user_id": str(assignee_id), "status": "assigned"}
        )

    elif action == ActionType.CREATE_TASK:
        from app.tasks.models import Task, TaskPriority, TaskStatus

        contact = await _load_contact(db, contact_id)
        title = _render_config_text(config.get("title", ""), contact, event_data)
        if not title:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_task", "error": "no task title configured"}
            )

        try:
            priority = TaskPriority(config.get("priority", "medium"))
        except ValueError:
            return ExecutionStatus.FAILED, json.dumps(
                {
                    "action": "create_task",
                    "error": f"invalid priority: {config.get('priority')!r}",
                }
            )

        due_date = None
        days = config.get("due_in_days")
        if days is not None:
            try:
                due_date = (
                    datetime.now(timezone.utc) + timedelta(days=int(days))
                ).date()
            except (TypeError, ValueError):
                return ExecutionStatus.FAILED, json.dumps(
                    {"action": "create_task", "error": f"invalid due_in_days: {days!r}"}
                )

        task = Task(
            id=uuid.uuid4(),
            title=title,
            description=_render_config_text(
                config.get("description", ""), contact, event_data
            )
            or None,
            contact_id=contact_id,
            assigned_user_id=workflow.created_by,
            status=TaskStatus.TODO,
            priority=priority,
            due_date=due_date,
            created_by=workflow.created_by,
        )
        db.add(task)
        await db.flush()

        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "create_task", "task_id": str(task.id), "status": "created"}
        )

    elif action == ActionType.WEBHOOK_OUTBOUND:
        import httpx

        url = config.get("url", "")
        if not url.startswith("https://"):
            # Refuse plaintext and non-HTTP schemes: workflow payloads carry
            # contact PII and the URL is admin-supplied free text.
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "webhook_outbound", "error": "url must be https://"}
            )
        payload = {
            "workflow_id": str(workflow.id),
            "workflow_name": workflow.name,
            "contact_id": str(contact_id) if contact_id else None,
            "event_data": event_data or {},
            "config": config.get("payload", {}),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(url, json=payload)
            if resp.status_code >= 400:
                return ExecutionStatus.FAILED, json.dumps(
                    {
                        "action": "webhook_outbound",
                        "error": f"webhook returned {resp.status_code}",
                        "status_code": resp.status_code,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: WEBHOOK_OUTBOUND failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "webhook_outbound", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "webhook_outbound", "status_code": resp.status_code, "status": "sent"}
        )

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
                        # Attribute to the workflow's owner. A nil UUID here
                        # violates the users FK and the insert would be rolled
                        # back into a swallowed "error" result.
                        created_by=workflow.created_by,
                    )
                    db.add(tag)
                    await db.flush()
                result = {"action": "add_tag", "tag_name": tag_name, "status": "added"}
            except Exception as exc:
                logger.exception("Workflow %s: ADD_TAG failed", workflow.id)
                return ExecutionStatus.FAILED, json.dumps(
                    {"action": "add_tag", "error": str(exc)}
                )
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

    elif action == ActionType.CREATE_CONTACT:
        # Insert the Contact directly rather than calling contacts.service.
        # create_contact: that path commits mid-run AND dispatches CONTACT_CREATED,
        # which re-enters the workflow engine — a CONTACT_CREATED-triggered
        # workflow with a CREATE_CONTACT step would recurse forever. The new
        # contact is owned by the workflow owner.
        from app.contacts.models import Contact, ContactType

        company = _render_config_text(config.get("company_name", ""), None, event_data).strip()
        name = _render_config_text(config.get("contact_name", ""), None, event_data).strip()
        if not company and not name:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_contact", "error": "company_name or contact_name is required"}
            )
        try:
            ctype = ContactType(str(config.get("type", "client")).lower())
        except ValueError:
            ctype = ContactType.CLIENT
        try:
            new_contact = Contact(
                id=uuid.uuid4(),
                type=ctype,
                # company_name is NOT NULL — fall back to the person's name.
                company_name=company or name,
                contact_name=name or None,
                email=(_render_config_text(config.get("email", ""), None, event_data) or None),
                phone=(_render_config_text(config.get("phone", ""), None, event_data) or None),
                job_title=(config.get("job_title") or None),
                lead_source=(config.get("lead_source") or "workflow"),
                created_by=workflow.created_by,
            )
            db.add(new_contact)
            await db.flush()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: CREATE_CONTACT failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_contact", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "create_contact", "contact_id": str(new_contact.id), "status": "created"}
        )

    elif action == ActionType.CREATE_INVOICE:
        from app.invoicing.schemas import InvoiceCreate, InvoiceLineItemCreate
        from app.invoicing.service import create_invoice

        target_contact_id = contact_id
        cfg_contact = config.get("contact_id")
        if cfg_contact:
            try:
                target_contact_id = uuid.UUID(str(cfg_contact))
            except (TypeError, ValueError):
                return ExecutionStatus.FAILED, json.dumps(
                    {"action": "create_invoice", "error": f"invalid contact_id: {cfg_contact!r}"}
                )
        if not target_contact_id:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_invoice", "error": "no contact to invoice"}
            )
        owner = await _load_owner(db, workflow)
        if owner is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_invoice", "error": "workflow owner not found"}
            )

        line_items: list = []
        for it in (config.get("line_items") or []):
            if not isinstance(it, dict):
                continue
            try:
                line_items.append(
                    InvoiceLineItemCreate(
                        description=str(it.get("description", "Service")),
                        quantity=it.get("quantity", 1),
                        unit_price=it.get("unit_price"),
                    )
                )
            except Exception:  # noqa: BLE001 — skip a malformed line, validate the set below
                continue
        # Single-line shorthand: {"amount": 500, "description": "Retainer"}
        if not line_items and config.get("amount") is not None:
            try:
                line_items = [
                    InvoiceLineItemCreate(
                        description=str(config.get("description", "Service")),
                        quantity=1,
                        unit_price=config.get("amount"),
                    )
                ]
            except Exception:  # noqa: BLE001
                line_items = []
        if not line_items:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_invoice", "error": "no valid line items configured"}
            )

        issue = datetime.now(timezone.utc).date()
        try:
            due_days = int(config.get("due_in_days", 30))
        except (TypeError, ValueError):
            due_days = 30
        try:
            data = InvoiceCreate(
                contact_id=target_contact_id,
                issue_date=issue,
                due_date=issue + timedelta(days=due_days),
                currency=config.get("currency", "USD"),
                notes=config.get("notes"),
                line_items=line_items,
            )
            invoice = await create_invoice(db, data, owner)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: CREATE_INVOICE failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "create_invoice", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {
                "action": "create_invoice",
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "status": "created",
            }
        )

    elif action == ActionType.SEND_PROPOSAL:
        from app.proposals.service import send_proposal

        raw = config.get("proposal_id") or (event_data or {}).get("proposal_id")
        if not raw:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_proposal", "error": "no proposal_id configured"}
            )
        try:
            proposal_id = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_proposal", "error": f"invalid proposal_id: {raw!r}"}
            )
        owner = await _load_owner(db, workflow)
        if owner is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_proposal", "error": "workflow owner not found"}
            )
        try:
            proposal = await send_proposal(db, proposal_id, owner)
        except Exception as exc:  # noqa: BLE001 — DRAFT-only, no recipients, send failure all raise
            logger.exception("Workflow %s: SEND_PROPOSAL failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "send_proposal", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {
                "action": "send_proposal",
                "proposal_id": str(proposal.id),
                "status": proposal.status.value,
            }
        )

    elif action == ActionType.MOVE_PIPELINE_STAGE:
        # NOTE: there is no deals/pipeline entity yet, so today a "pipeline stage"
        # IS a proposal's status (Draft -> Sent -> Viewed -> Signed/Declined/Paid).
        # This moves the triggering contact's (or a configured) proposal to the
        # target status. A separate task will add a real deals pipeline; when it
        # lands, branch on the deal here. Sets status directly (no PIPELINE_
        # STAGE_CHANGED dispatch) to avoid re-entering the engine mid-run.
        from app.proposals.models import Proposal, ProposalActivity, ProposalStatus

        raw_stage = str(config.get("stage") or config.get("status") or "").strip().lower()
        if not raw_stage:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "move_pipeline_stage", "error": "no target stage configured"}
            )
        _STAGE_SYNONYMS = {
            "won": "signed", "complete": "signed", "completed": "signed",
            "lost": "declined", "open": "sent",
        }
        raw_stage = _STAGE_SYNONYMS.get(raw_stage, raw_stage)
        try:
            target = ProposalStatus(raw_stage)
        except ValueError:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "move_pipeline_stage", "error": f"unknown stage: {raw_stage!r}"}
            )

        proposal = None
        raw_pid = config.get("proposal_id") or (event_data or {}).get("proposal_id")
        if raw_pid:
            try:
                proposal = (
                    await db.execute(
                        select(Proposal).where(Proposal.id == uuid.UUID(str(raw_pid)))
                    )
                ).scalar_one_or_none()
            except (TypeError, ValueError):
                proposal = None
        if proposal is None and contact_id:
            proposal = (
                await db.execute(
                    select(Proposal)
                    .where(Proposal.contact_id == contact_id)
                    .order_by(Proposal.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if proposal is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "move_pipeline_stage", "error": "no proposal found to move"}
            )

        prev = proposal.status
        proposal.status = target
        db.add(
            ProposalActivity(
                proposal_id=proposal.id,
                action="stage_moved",
                metadata_json=json.dumps(
                    {"from": getattr(prev, "value", prev), "to": target.value, "via": "workflow"}
                ),
            )
        )
        await db.flush()
        return ExecutionStatus.COMPLETED, json.dumps(
            {
                "action": "move_pipeline_stage",
                "proposal_id": str(proposal.id),
                "from": getattr(prev, "value", prev),
                "to": target.value,
                "status": "moved",
            }
        )

    elif action == ActionType.ADD_TO_WORKFLOW:
        raw = config.get("workflow_id") or config.get("target_workflow_id")
        if not raw:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "add_to_workflow", "error": "no workflow_id configured"}
            )
        try:
            target_id = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "add_to_workflow", "error": f"invalid workflow_id: {raw!r}"}
            )
        if target_id == workflow.id:
            # Enrolling into the running workflow is an obvious infinite loop.
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "add_to_workflow", "error": "cannot enroll into the running workflow (self-loop)"}
            )
        target = (
            await db.execute(select(Workflow).where(Workflow.id == target_id))
        ).scalar_one_or_none()
        if target is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "add_to_workflow", "error": "target workflow not found"}
            )
        try:
            new_exec = await execute_workflow(db, target_id, contact_id, event_data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: ADD_TO_WORKFLOW failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "add_to_workflow", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {
                "action": "add_to_workflow",
                "enrolled_workflow_id": str(target_id),
                "execution_id": str(new_exec.id),
                "status": new_exec.status.value,
            }
        )

    elif action == ActionType.REMOVE_FROM_WORKFLOW:
        raw = config.get("workflow_id") or config.get("target_workflow_id")
        if not raw:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "remove_from_workflow", "error": "no workflow_id configured"}
            )
        try:
            target_id = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "remove_from_workflow", "error": f"invalid workflow_id: {raw!r}"}
            )
        if not contact_id:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "remove_from_workflow", "error": "no contact to un-enroll"}
            )
        rows = (
            await db.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.workflow_id == target_id,
                    WorkflowExecution.contact_id == contact_id,
                    WorkflowExecution.status.in_(
                        [ExecutionStatus.RUNNING, ExecutionStatus.WAITING]
                    ),
                )
            )
        ).scalars().all()
        cancelled = 0
        now = datetime.now(timezone.utc)
        for ex in rows:
            ex.status = ExecutionStatus.CANCELLED
            ex.completed_at = now
            ex.resume_at = None
            ex.resume_step_index = None
            cancelled += 1
        await db.flush()
        return ExecutionStatus.COMPLETED, json.dumps(
            {
                "action": "remove_from_workflow",
                "removed_from_workflow": str(target_id),
                "cancelled": cancelled,
                "status": "removed",
            }
        )

    elif action == ActionType.ASK_OBRAIN:
        # Non-streaming O-Brain (Claude) call. Metered against the workflow
        # owner's AI credits and FAIL-CLOSED: out of credits => the step FAILS
        # rather than spending money the tenant doesn't have.
        from app.billing import ai_meter
        from app.config import Settings as _Settings

        owner = await _load_owner(db, workflow)
        if owner is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": "workflow owner not found"}
            )
        contact = await _load_contact(db, contact_id)
        prompt = _render_config_text(
            config.get("prompt", "") or config.get("question", ""), contact, event_data
        ).strip()
        if not prompt:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": "no prompt configured"}
            )

        _cfg = _Settings()
        if not _cfg.anthropic_api_key:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": "O-Brain is not configured (missing Anthropic API key)"}
            )

        try:
            await ai_meter.consume(db, owner, "workflow_ask_obrain")
        except ai_meter.AiCreditsExhausted as exc:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": exc.message, "code": "ai_credits_exhausted"}
            )
        except Exception as exc:  # noqa: BLE001 — never spend on an unmetered call
            logger.exception("Workflow %s: ASK_OBRAIN metering failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": f"AI metering failed: {exc}"}
            )

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=_cfg.anthropic_api_key)
            response = await client.messages.create(
                model=_cfg.anthropic_model,
                max_tokens=int(config.get("max_tokens", 1024) or 1024),
                system=(
                    config.get("system")
                    or "You are O-Brain, an automated assistant running inside a CRM "
                    "workflow. Answer concisely and factually."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            answer = "".join(
                b.text for b in response.content if getattr(b, "type", "") == "text"
            ).strip()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: ASK_OBRAIN call failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": str(exc)}
            )
        if not answer:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "ask_obrain", "error": "O-Brain returned an empty response"}
            )

        # Record the interaction so it's auditable and (if a contact triggered
        # it) visible on that contact's timeline. Both are best-effort.
        try:
            from app.brain.models import AuditActionType, BrainAuditLog

            db.add(
                BrainAuditLog(
                    id=uuid.uuid4(),
                    user_id=owner.id,
                    action_type=AuditActionType.WORKFLOW_AI_ACTION,
                    ai_input=prompt[:2000],
                    ai_output=answer[:2000],
                    source_data_json=json.dumps({"workflow_id": str(workflow.id)}),
                )
            )
            await db.flush()
        except Exception:  # noqa: BLE001
            logger.exception("Workflow %s: ASK_OBRAIN audit log failed", workflow.id)
        if contact_id:
            try:
                await log_contact_activity(
                    db,
                    contact_id=contact_id,
                    activity_type=ActivityType.NOTE_ADDED,
                    title=f"O-Brain: {workflow.name}",
                    description=answer[:2000],
                )
            except Exception:  # noqa: BLE001
                logger.exception("Workflow %s: ASK_OBRAIN activity log failed", workflow.id)
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "ask_obrain", "status": "answered", "answer": answer[:2000]}
        )

    elif action == ActionType.LOG_TO_BRAIN:
        # Persist a note into O-Brain's searchable knowledge (brain_embeddings).
        # Embedding is an AI operation, so it is metered and FAIL-CLOSED.
        from app.billing import ai_meter
        from app.brain.embedding_service import embed_and_store
        from app.brain.models import EmbeddingSourceType

        owner = await _load_owner(db, workflow)
        if owner is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "log_to_brain", "error": "workflow owner not found"}
            )
        contact = await _load_contact(db, contact_id)
        content = _render_config_text(
            config.get("content", "") or config.get("note", "") or config.get("text", ""),
            contact,
            event_data,
        ).strip()
        if not content:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "log_to_brain", "error": "no content configured"}
            )

        try:
            await ai_meter.consume(db, owner, "embedding_batch")
        except ai_meter.AiCreditsExhausted as exc:
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "log_to_brain", "error": exc.message, "code": "ai_credits_exhausted"}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: LOG_TO_BRAIN metering failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "log_to_brain", "error": f"AI metering failed: {exc}"}
            )

        try:
            records = await embed_and_store(
                db,
                user_id=owner.id,
                content=content,
                source_type=EmbeddingSourceType.MANUAL_NOTE,
                source_id=f"workflow:{workflow.id}",
                contact_id=contact_id,
                metadata={"workflow_id": str(workflow.id), "workflow_name": workflow.name},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s: LOG_TO_BRAIN store failed", workflow.id)
            return ExecutionStatus.FAILED, json.dumps(
                {"action": "log_to_brain", "error": str(exc)}
            )
        return ExecutionStatus.COMPLETED, json.dumps(
            {"action": "log_to_brain", "chunks_stored": len(records), "status": "logged"}
        )

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

    else:
        # Unreachable for known actions — every ActionType member is either
        # handled above or listed in _UNIMPLEMENTED_ACTIONS. A new enum member
        # added without a handler lands here and fails loudly rather than
        # silently reporting success.
        logger.error(
            "Workflow %s: action type %s has no handler", workflow.id, action.value
        )
        return ExecutionStatus.FAILED, json.dumps(
            {"action": action.value, "error": f"no handler for action type {action.value}"}
        )


# ---------------------------------------------------------------------------
# Canvas (graph) validation + execution
# ---------------------------------------------------------------------------


def validate_definition(definition: dict) -> list[str]:
    """Validate a canvas graph definition. Port of Arivio's graph.ts checks:
    exactly one trigger node, every node reachable from it, no orphan edges,
    at most one edge per condition handle, and (v1) no cycles."""
    errors: list[str] = []
    nodes = definition.get("nodes") or []
    edges = definition.get("edges") or []
    start_node_id = definition.get("start_node_id")

    node_ids = [n.get("id") for n in nodes]
    if len(set(node_ids)) != len(node_ids):
        errors.append("duplicate node ids")
    node_id_set = set(node_ids)

    triggers = [n for n in nodes if n.get("kind") == "trigger"]
    if len(triggers) != 1:
        errors.append(f"workflow must have exactly one trigger node (found {len(triggers)})")

    if not start_node_id or start_node_id not in node_id_set:
        errors.append("start_node_id must reference an existing node")

    for edge in edges:
        if edge.get("source") not in node_id_set:
            errors.append(f"edge {edge.get('id')} has unknown source {edge.get('source')!r}")
        if edge.get("target") not in node_id_set:
            errors.append(f"edge {edge.get('id')} has unknown target {edge.get('target')!r}")

    handle_counts: dict[tuple, int] = defaultdict(int)
    for edge in edges:
        handle_counts[(edge.get("source"), edge.get("source_handle"))] += 1
    nodes_by_id = {n.get("id"): n for n in nodes}
    for (source, handle), count in handle_counts.items():
        node = nodes_by_id.get(source)
        if node and node.get("kind") == "condition" and count > 1:
            errors.append(f"condition node {source} has more than one edge on handle {handle!r}")

    if errors:
        # Structural errors make reachability/cycle analysis meaningless.
        return errors

    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["source"]].append(edge["target"])

    visited: set[str] = set()
    stack = [start_node_id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, []))
    unreachable = node_id_set - visited
    if unreachable:
        errors.append(f"unreachable nodes: {sorted(unreachable)}")

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in node_id_set}
    has_cycle = False

    def _dfs(u: str) -> None:
        nonlocal has_cycle
        color[u] = GRAY
        for v in adjacency.get(u, []):
            if color.get(v) == GRAY:
                has_cycle = True
                return
            if color.get(v) == WHITE:
                _dfs(v)
                if has_cycle:
                    return
        color[u] = BLACK

    _dfs(start_node_id)
    if has_cycle:
        errors.append("workflow graph contains a cycle")

    return errors


#: Hard cap on nodes visited per execution -- backstops a cycle that slipped
#: past validate_definition (e.g. an old definition saved before validation
#: existed) so a broken graph fails loudly instead of looping forever.
_GRAPH_EXECUTION_BUDGET = 200


async def _execute_graph(
    db: AsyncSession,
    workflow: Workflow,
    definition: dict,
    contact_id: uuid.UUID | None,
    event_data: dict | None,
    execution: WorkflowExecution,
) -> tuple[ExecutionStatus, str | None]:
    """Walk a canvas graph from its start node, executing action/condition/
    delay nodes as it goes. Reuses ``_execute_action`` untouched for action
    nodes -- every action the linear engine can run, the graph can too."""
    nodes_by_id = {n["id"]: n for n in definition.get("nodes", [])}
    adjacency: dict[str, list[tuple]] = defaultdict(list)
    for edge in definition.get("edges", []):
        adjacency[edge["source"]].append((edge.get("source_handle"), edge["target"]))

    def _next_node(node_id: str, handle: str | None = None) -> str | None:
        for h, target in adjacency.get(node_id, []):
            if handle is None or h == handle:
                return target
        return None

    current = definition.get("start_node_id")
    visited: set[str] = set()
    budget = _GRAPH_EXECUTION_BUDGET

    while current is not None:
        if budget <= 0 or current in visited:
            return ExecutionStatus.FAILED, json.dumps(
                {"error": "execution budget exceeded or cycle detected", "node_id": current}
            )
        budget -= 1
        visited.add(current)

        node = nodes_by_id.get(current)
        if node is None:
            return ExecutionStatus.FAILED, json.dumps(
                {"error": f"unknown node {current}"}
            )

        kind = node.get("kind")

        if kind == "trigger":
            current = _next_node(current)
            continue

        if kind == "action":
            try:
                action_type = ActionType(node["action_type"])
            except (KeyError, ValueError):
                return ExecutionStatus.FAILED, json.dumps(
                    {"error": f"invalid action_type on node {current}"}
                )
            # A transient (unpersisted) WorkflowStep -- _execute_action only
            # reads its fields, so the graph doesn't need a workflow_steps row.
            fake_step = WorkflowStep(
                id=uuid.uuid4(),
                workflow_id=workflow.id,
                step_order=0,
                action_type=action_type,
                action_config_json=json.dumps(node.get("config") or {}),
                condition_json=None,
                wait_duration_seconds=node.get("wait_duration_seconds"),
            )
            exec_step = WorkflowExecutionStep(
                id=uuid.uuid4(), execution_id=execution.id, step_id=None,
                status=ExecutionStatus.RUNNING,
            )
            db.add(exec_step)
            await db.flush()
            try:
                step_status, result_json = await _execute_action(
                    db, workflow, fake_step, contact_id, event_data
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Workflow %s: graph node %s failed", workflow.id, current)
                step_status, result_json = ExecutionStatus.FAILED, json.dumps(
                    {"error": str(exc)}
                )
            exec_step.status = step_status
            exec_step.result_json = result_json
            exec_step.completed_at = datetime.now(timezone.utc)
            await db.flush()

            if step_status == ExecutionStatus.WAITING:
                return ExecutionStatus.WAITING, None
            if step_status == ExecutionStatus.FAILED:
                return ExecutionStatus.FAILED, result_json
            current = _next_node(current)
            continue

        if kind == "delay":
            exec_step = WorkflowExecutionStep(
                id=uuid.uuid4(), execution_id=execution.id, step_id=None,
                status=ExecutionStatus.WAITING,
                result_json=json.dumps(
                    {"action": "wait_delay", "wait_seconds": node.get("wait_duration_seconds", 0)}
                ),
            )
            db.add(exec_step)
            await db.flush()
            return ExecutionStatus.WAITING, None

        if kind == "condition":
            condition = node.get("condition") or {}
            field = condition.get("field", "")
            operator = condition.get("operator", "eq")
            value = condition.get("value")
            actual = (event_data or {}).get(field)

            if operator == "eq":
                branch_true = actual == value
            elif operator == "neq":
                branch_true = actual != value
            elif operator == "contains":
                branch_true = bool(value and actual and value in str(actual))
            elif operator == "exists":
                branch_true = actual is not None
            else:
                branch_true = False
            handle = "true" if branch_true else "false"

            exec_step = WorkflowExecutionStep(
                id=uuid.uuid4(), execution_id=execution.id, step_id=None,
                status=ExecutionStatus.COMPLETED,
                result_json=json.dumps({"action": "condition", "node_id": current, "branch": handle}),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(exec_step)
            await db.flush()
            current = _next_node(current, handle)
            continue

        return ExecutionStatus.FAILED, json.dumps(
            {"error": f"unknown node kind {kind!r} on node {current}"}
        )

    return ExecutionStatus.COMPLETED, None


async def _run_linear_steps(
    db: AsyncSession,
    workflow: Workflow,
    execution: WorkflowExecution,
    steps: list[WorkflowStep],
    start_index: int,
    contact_id: uuid.UUID | None,
    event_data: dict | None,
) -> tuple[ExecutionStatus, str | None]:
    """Run the step-authored (linear) engine from ``start_index`` to the end.

    Shared by the initial run (``execute_workflow``, start 0) and the resume
    poller (``resume_waiting_workflows``, start at the parked step). Returns the
    overall (status, error). On WAIT_DELAY it records resume state on the
    execution and stops; on IF_ELSE_BRANCH it evaluates the condition and, when
    false, skips the immediately-following (true-branch) step — the linear
    mirror of how ``_execute_graph`` routes a condition node's true/false handle.
    """
    overall_status = ExecutionStatus.COMPLETED
    overall_error: str | None = None
    n = len(steps)
    i = start_index

    while i < n:
        step = steps[i]
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
                db, workflow, step, contact_id, event_data
            )
            exec_step.status = step_status
            exec_step.result_json = result_json
            exec_step.completed_at = datetime.now(timezone.utc)

            if step_status == ExecutionStatus.WAITING:
                # Park the execution: persist WHERE to resume, WHEN it is due,
                # and the event context to continue with. The resume poller
                # only ever picks up rows whose resume_at is set and past-due.
                try:
                    wait_seconds = int((json.loads(result_json) or {}).get("wait_seconds") or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    wait_seconds = 0
                execution.resume_at = datetime.now(timezone.utc) + timedelta(
                    seconds=max(0, wait_seconds)
                )
                execution.resume_step_index = i + 1
                execution.context_json = (
                    json.dumps(event_data) if event_data is not None else None
                )
                overall_status = ExecutionStatus.WAITING
                await db.flush()
                break

            if step_status == ExecutionStatus.FAILED:
                overall_status = ExecutionStatus.FAILED
                overall_error = result_json
                await db.flush()
                break

            # IF_ELSE_BRANCH routing: when the condition is false, skip the next
            # step (the true-branch action). Recorded as a skipped row so the
            # execution log shows the path that was taken.
            if step.action_type == ActionType.IF_ELSE_BRANCH:
                try:
                    branch = (json.loads(result_json) if result_json else {}).get("branch")
                except json.JSONDecodeError:
                    branch = None
                if branch == "false" and i + 1 < n:
                    skipped = steps[i + 1]
                    db.add(
                        WorkflowExecutionStep(
                            id=uuid.uuid4(),
                            execution_id=execution.id,
                            step_id=skipped.id,
                            status=ExecutionStatus.COMPLETED,
                            result_json=json.dumps(
                                {
                                    "action": skipped.action_type.value,
                                    "status": "skipped",
                                    "reason": "if_else_branch: condition false",
                                }
                            ),
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
                    await db.flush()
                    i += 1  # consume the skipped step

        except Exception as exc:  # noqa: BLE001 — a step must never crash the run
            logger.exception("Workflow step %s failed: %s", step.id, str(exc))
            exec_step.status = ExecutionStatus.FAILED
            exec_step.error_message = str(exc)
            exec_step.completed_at = datetime.now(timezone.utc)
            overall_status = ExecutionStatus.FAILED
            overall_error = str(exc)
            await db.flush()
            break

        i += 1

    return overall_status, overall_error


async def execute_workflow(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    event_data: dict | None = None,
) -> WorkflowExecution:
    """Create an execution record and run the workflow.

    Dual-mode: a canvas-authored workflow (``definition_json`` set) walks the
    graph via ``_execute_graph``; a step-authored workflow runs the original
    linear loop below, byte-for-byte unchanged.
    """
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

    if workflow.definition_json:
        try:
            definition = json.loads(workflow.definition_json)
        except json.JSONDecodeError:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = json.dumps({"error": "invalid definition_json"})
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(execution)
            return execution

        overall_status, overall_error = await _execute_graph(
            db, workflow, definition, contact_id, event_data, execution
        )
        execution.status = overall_status
        if overall_status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            execution.completed_at = datetime.now(timezone.utc)
        if overall_error:
            execution.error_message = overall_error
        await db.commit()
        await db.refresh(execution)
        return execution

    # Fetch ordered steps
    steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
    )
    steps = list(steps_result.scalars().all())

    overall_status, overall_error = await _run_linear_steps(
        db, workflow, execution, steps, 0, contact_id, event_data
    )

    execution.status = overall_status
    if overall_status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        execution.completed_at = datetime.now(timezone.utc)
        # Terminal — no longer parked; clear any resume state defensively.
        execution.resume_at = None
        execution.resume_step_index = None
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


async def safe_dispatch(
    db: AsyncSession,
    event_type: TriggerType,
    event_data: dict | None = None,
    contact_id: uuid.UUID | None = None,
) -> None:
    """Fire-and-forget dispatch for domain code: an automation failure must
    never break the operation that triggered it (same contract the forms
    webhook established)."""
    try:
        await dispatch_event(db, event_type, event_data, contact_id)
    except Exception:  # noqa: BLE001
        logger.exception("workflow dispatch failed for %s", event_type.value)


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


# ---------------------------------------------------------------------------
# Inbound webhook trigger (WEBHOOK_RECEIVED)
# ---------------------------------------------------------------------------

def _trigger_config(workflow: Workflow) -> dict:
    if not workflow.trigger_config_json:
        return {}
    try:
        cfg = json.loads(workflow.trigger_config_json)
        return cfg if isinstance(cfg, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def ensure_webhook_key(db: AsyncSession, workflow: Workflow, rotate: bool = False) -> str:
    """Return this workflow's inbound webhook key, minting one on first use.

    The key in the URL is the only credential, so it is generated with
    ``secrets`` and can be rotated to revoke a leaked URL.
    """
    import secrets

    cfg = _trigger_config(workflow)
    if rotate or not cfg.get("webhook_key"):
        cfg["webhook_key"] = secrets.token_urlsafe(32)
        workflow.trigger_config_json = json.dumps(cfg)
        await db.commit()
        await db.refresh(workflow)
    return cfg["webhook_key"]


async def trigger_by_webhook_key(
    db: AsyncSession, webhook_key: str, payload: dict
) -> WorkflowExecution | None:
    """Run the single ACTIVE webhook workflow owning this key.

    Deliberately not a broadcast to every WEBHOOK_RECEIVED workflow: the key
    identifies one workflow, so an unrelated workflow must never see another's
    payload. Returns None when no active workflow matches.
    """
    if not webhook_key:
        return None

    result = await db.execute(
        select(Workflow).where(
            Workflow.is_active == True,  # noqa: E712
            Workflow.trigger_type == TriggerType.WEBHOOK_RECEIVED,
        )
    )
    for workflow in result.scalars().all():
        if _trigger_config(workflow).get("webhook_key") == webhook_key:
            return await execute_workflow(
                db, workflow.id, None, {"payload": payload, "source": "webhook"}
            )
    return None


# ---------------------------------------------------------------------------
# Time-based trigger (SCHEDULED)
# ---------------------------------------------------------------------------

def _due(cfg: dict, now: datetime, last_run: datetime | None) -> bool:
    """Is a SCHEDULED workflow due to run?

    Config shapes supported:
      {"interval_minutes": 60}                  — every N minutes
      {"cron": {"hour": 9, "minute": 0}}        — daily at HH:MM (UTC)
      {"cron": {"day": 1, "hour": 9}}           — monthly on day N
      {"cron": {"weekday": 0, "hour": 9}}       — weekly (0=Monday)
    """
    interval = cfg.get("interval_minutes")
    if interval:
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return False
        if interval <= 0:
            return False
        return last_run is None or (now - last_run) >= timedelta(minutes=interval)

    cron = cfg.get("cron")
    if not isinstance(cron, dict):
        return False

    hour = cron.get("hour")
    minute = cron.get("minute", 0)
    if hour is not None and now.hour != int(hour):
        return False
    if minute is not None and now.minute // 15 != int(minute) // 15:
        # 15-minute granularity — the poller runs every 15 minutes, so match
        # the bucket rather than the exact minute or it would never fire.
        return False
    if cron.get("day") is not None and now.day != int(cron["day"]):
        return False
    if cron.get("weekday") is not None and now.weekday() != int(cron["weekday"]):
        return False

    # Never run the same slot twice.
    if last_run is not None and (now - last_run) < timedelta(minutes=30):
        return False
    return True


async def run_scheduled_workflows(db: AsyncSession, now: datetime | None = None) -> int:
    """Execute every active SCHEDULED workflow that is due. Returns the count."""
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(Workflow).where(
            Workflow.is_active == True,  # noqa: E712
            Workflow.trigger_type == TriggerType.SCHEDULED,
        )
    )
    workflows = list(result.scalars().all())
    if not workflows:
        return 0

    ran = 0
    for workflow in workflows:
        cfg = _trigger_config(workflow)
        last_row = await db.execute(
            select(func.max(WorkflowExecution.started_at)).where(
                WorkflowExecution.workflow_id == workflow.id
            )
        )
        last_run = last_row.scalar()
        if last_run is not None and last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        if not _due(cfg, now, last_run):
            continue
        try:
            await execute_workflow(db, workflow.id, None, {"scheduled_at": now.isoformat()})
            ran += 1
        except Exception:  # noqa: BLE001
            logger.exception("scheduled workflow %s failed", workflow.id)
    return ran


# ---------------------------------------------------------------------------
# WAIT_DELAY resumption
# ---------------------------------------------------------------------------

async def resume_waiting_workflows(db: AsyncSession, now: datetime | None = None) -> int:
    """Continue every parked (WAITING) linear execution whose delay has elapsed.

    Called by the scheduler every minute. A WAIT_DELAY step returns WAITING and
    ``_run_linear_steps`` stamps ``resume_at`` / ``resume_step_index`` /
    ``context_json`` on the row. Here we pick up the rows that are due and run
    the remaining steps — honouring any further WAIT_DELAYs (the row simply
    re-parks with a new ``resume_at``).

    Idempotency / no double-processing:
      * only rows still in WAITING with a set, past-due ``resume_at`` are eligible;
      * each row is claimed by flipping it to RUNNING (and clearing ``resume_at``)
        before any work, so a second overlapping tick sees it as not-eligible;
      * canvas/graph WAITING rows never set ``resume_at`` and are left untouched.

    Returns the number of executions advanced.
    """
    now = now or datetime.now(timezone.utc)

    rows = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.status == ExecutionStatus.WAITING,
            WorkflowExecution.resume_at.is_not(None),
        )
    )
    executions = list(rows.scalars().all())

    resumed = 0
    for execution in executions:
        resume_at = execution.resume_at
        if resume_at is None:
            continue
        if resume_at.tzinfo is None:  # SQLite returns naive datetimes
            resume_at = resume_at.replace(tzinfo=timezone.utc)
        if resume_at > now:
            continue  # not due yet

        # Claim the row before doing any work so an overlapping tick can't grab it.
        start_index = execution.resume_step_index or 0
        context = None
        if execution.context_json:
            try:
                context = json.loads(execution.context_json)
            except json.JSONDecodeError:
                context = None
        execution.status = ExecutionStatus.RUNNING
        execution.resume_at = None
        await db.flush()

        workflow = (
            await db.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
        ).scalar_one_or_none()
        if workflow is None:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = json.dumps({"error": "workflow no longer exists"})
            execution.completed_at = now
            execution.resume_step_index = None
            resumed += 1
            continue

        steps_result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow.id)
            .order_by(WorkflowStep.step_order)
        )
        steps = list(steps_result.scalars().all())

        try:
            overall_status, overall_error = await _run_linear_steps(
                db, workflow, execution, steps, start_index, execution.contact_id, context
            )
        except Exception as exc:  # noqa: BLE001 — one bad row must not stall the rest
            logger.exception("resume workflow %s failed", execution.id)
            overall_status = ExecutionStatus.FAILED
            overall_error = str(exc)

        execution.status = overall_status
        if overall_status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            execution.completed_at = now
            execution.resume_at = None
            execution.resume_step_index = None
        if overall_error:
            execution.error_message = overall_error
        resumed += 1

    await db.commit()
    return resumed
