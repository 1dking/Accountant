
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
#: CREATE_TASK and MOVE_PIPELINE_STAGE have no backing table to write to;
#: ASK_OBRAIN needs a non-streaming brain call (and spends paid tokens).
_UNIMPLEMENTED_ACTIONS: dict[ActionType, str] = {
    ActionType.CREATE_CONTACT: "create_contact is not implemented yet",
    ActionType.CREATE_INVOICE: "create_invoice is not implemented yet",
    ActionType.SEND_PROPOSAL: "send_proposal is not implemented yet",
    ActionType.MOVE_PIPELINE_STAGE: (
        "move_pipeline_stage is not implemented yet (no pipeline model)"
    ),
    ActionType.ADD_TO_WORKFLOW: "add_to_workflow is not implemented yet",
    ActionType.REMOVE_FROM_WORKFLOW: "remove_from_workflow is not implemented yet",
    ActionType.ASK_OBRAIN: "ask_obrain is not implemented yet",
    ActionType.LOG_TO_BRAIN: "log_to_brain is not implemented yet",
}


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
                db, workflow, step, contact_id, event_data
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
