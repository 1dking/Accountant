"""Tasks — the CRM to-do list.

No task table existed at all, which is why the contact "Tasks" tab was a
placeholder and the workflow engine's CREATE_TASK action had nothing to write
to and failed as unimplemented.
"""
import json
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.tasks.models import Task, TaskPriority, TaskStatus
from app.tasks.schemas import TaskCreate, TaskUpdate
from app.tasks.service import create_task, list_tasks, update_task
from tests.conftest import auth_header


@pytest.mark.high
async def test_create_and_list_task_for_a_contact(db, admin_user: User, sample_contact):
    await create_task(
        db,
        TaskCreate(title="Call Dana back", contact_id=sample_contact.id),
        admin_user,
    )

    rows = await list_tasks(db, admin_user, contact_id=sample_contact.id)
    assert len(rows) == 1
    assert rows[0].title == "Call Dana back"
    assert rows[0].status == TaskStatus.TODO
    assert rows[0].priority == TaskPriority.MEDIUM


@pytest.mark.high
async def test_task_can_stand_alone_without_a_contact(db, admin_user: User):
    """contact_id is nullable on purpose — "renew the domain" belongs to nobody."""
    task = await create_task(db, TaskCreate(title="Renew the domain"), admin_user)
    assert task.contact_id is None

    rows = await list_tasks(db, admin_user)
    assert [t.title for t in rows] == ["Renew the domain"]


@pytest.mark.high
async def test_dated_tasks_sort_ahead_of_undated_ones(db, admin_user: User):
    """An undated task must not outrank one due tomorrow."""
    await create_task(db, TaskCreate(title="Someday"), admin_user)
    await create_task(
        db,
        TaskCreate(title="Due tomorrow", due_date=date.today() + timedelta(days=1)),
        admin_user,
    )

    rows = await list_tasks(db, admin_user)
    assert [t.title for t in rows] == ["Due tomorrow", "Someday"]


@pytest.mark.high
async def test_completing_and_reopening_tracks_completed_at(db, admin_user: User):
    task = await create_task(db, TaskCreate(title="Ship it"), admin_user)
    assert task.completed_at is None

    task = await update_task(
        db, task.id, TaskUpdate(status=TaskStatus.DONE), admin_user
    )
    assert task.completed_at is not None

    # Reopening must clear it, or the timeline shows a completion that was undone.
    task = await update_task(
        db, task.id, TaskUpdate(status=TaskStatus.TODO), admin_user
    )
    assert task.completed_at is None


@pytest.mark.high
async def test_task_endpoints_round_trip(client, admin_user: User, sample_contact):
    resp = await client.post(
        "/api/tasks",
        json={
            "title": "Send the quote",
            "contact_id": str(sample_contact.id),
            "priority": "high",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/tasks?contact_id={sample_contact.id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()["data"]] == ["Send the quote"]

    resp = await client.patch(
        f"/api/tasks/{task_id}",
        json={"status": "done"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["completed_at"] is not None

    resp = await client.delete(
        f"/api/tasks/{task_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200


@pytest.mark.critical
async def test_tasks_require_authentication(client):
    assert (await client.get("/api/tasks")).status_code == 401


@pytest.mark.critical
async def test_workflow_create_task_action_now_creates_a_real_task(
    db, admin_user: User, sample_contact
):
    """CREATE_TASK used to fall through a catch-all that reported COMPLETED for
    doing nothing, then failed as unimplemented once there was no table."""
    from app.workflows.models import (
        ActionType,
        ExecutionStatus,
        TriggerType,
        Workflow,
        WorkflowExecutionStep,
        WorkflowStep,
    )
    from app.workflows.service import execute_workflow

    workflow = Workflow(
        id=uuid.uuid4(),
        name="Onboarding",
        trigger_type=TriggerType.CONTACT_CREATED,
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(workflow)
    await db.flush()
    db.add(
        WorkflowStep(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            step_order=1,
            action_type=ActionType.CREATE_TASK,
            action_config_json=json.dumps(
                {
                    "title": "Welcome {contact_name}",
                    "priority": "high",
                    "due_in_days": 3,
                }
            ),
        )
    )
    await db.commit()

    execution = await execute_workflow(db, workflow.id, contact_id=sample_contact.id)

    step = (
        await db.execute(
            select(WorkflowExecutionStep).where(
                WorkflowExecutionStep.execution_id == execution.id
            )
        )
    ).scalar_one()
    assert step.status == ExecutionStatus.COMPLETED

    task = (
        await db.execute(select(Task).where(Task.contact_id == sample_contact.id))
    ).scalar_one()
    assert task.title == f"Welcome {sample_contact.contact_name}"
    assert task.priority == TaskPriority.HIGH
    # The CREATE_TASK action computes due_date from UTC now(); asserting against
    # local date.today() flakes when the run straddles the UTC/local day boundary
    # (e.g. evening in the Americas). Accept the UTC-based date, tolerating a
    # one-day slop for a run that crosses midnight.
    from datetime import datetime, timezone

    expected = datetime.now(timezone.utc).date() + timedelta(days=3)
    assert abs((task.due_date - expected).days) <= 1
