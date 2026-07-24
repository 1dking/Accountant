"""Proves the previously-inert workflow triggers actually fire.

Seven TriggerTypes were defined but nothing dispatched them, so a user could
build a workflow on them and it would silently never run. Each test here builds
an ACTIVE workflow on one of those triggers and asserts an execution row is
created when the real domain event happens.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.workflows.models import (
    ActionType,
    TriggerType,
    Workflow,
    WorkflowExecution,
    WorkflowStep,
)


async def _make_workflow(
    db: AsyncSession,
    user: User,
    trigger: TriggerType,
    trigger_config: dict | None = None,
) -> Workflow:
    wf = Workflow(
        id=uuid.uuid4(),
        name=f"auto-{trigger.value}",
        trigger_type=trigger,
        trigger_config_json=json.dumps(trigger_config) if trigger_config else None,
        is_active=True,
        created_by=user.id,
    )
    db.add(wf)
    await db.flush()
    db.add(WorkflowStep(
        id=uuid.uuid4(),
        workflow_id=wf.id,
        step_order=1,
        action_type=ActionType.CREATE_NOTE,
        action_config_json=json.dumps({"title": "fired"}),
    ))
    await db.commit()
    await db.refresh(wf)
    return wf


async def _executions(db: AsyncSession, wf: Workflow) -> int:
    return await db.scalar(
        select(func.count()).select_from(WorkflowExecution).where(
            WorkflowExecution.workflow_id == wf.id
        )
    ) or 0


# ── APPOINTMENT_COMPLETED ────────────────────────────────────────────────


@pytest.mark.critical
async def test_appointment_completed_fires_for_past_booking(
    db: AsyncSession, admin_user: User
):
    """Nothing ever set a booking to COMPLETED, so this trigger had no source
    event. The scheduler job is now that source."""
    from app.scheduling.models import (
        BookingStatus,
        CalendarBooking,
        SchedulingCalendar,
    )
    from app.scheduling.service import complete_past_bookings

    wf = await _make_workflow(db, admin_user, TriggerType.APPOINTMENT_COMPLETED)

    cal = SchedulingCalendar(
        id=uuid.uuid4(), name="Cal", slug=f"cal-{uuid.uuid4().hex[:8]}",
        created_by=admin_user.id,
    )
    db.add(cal)
    await db.flush()

    now = datetime.now(timezone.utc)
    booking = CalendarBooking(
        id=uuid.uuid4(),
        calendar_id=cal.id,
        guest_name="Past Guest",
        guest_email="guest@example.com",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    await db.commit()

    done = await complete_past_bookings(db, now=now)
    assert done == 1
    await db.refresh(booking)
    assert booking.status == BookingStatus.COMPLETED
    assert await _executions(db, wf) == 1


@pytest.mark.normal
async def test_future_and_cancelled_bookings_are_left_alone(
    db: AsyncSession, admin_user: User
):
    from app.scheduling.models import (
        BookingStatus,
        CalendarBooking,
        SchedulingCalendar,
    )
    from app.scheduling.service import complete_past_bookings

    cal = SchedulingCalendar(
        id=uuid.uuid4(), name="Cal", slug=f"cal-{uuid.uuid4().hex[:8]}",
        created_by=admin_user.id,
    )
    db.add(cal)
    await db.flush()
    now = datetime.now(timezone.utc)
    db.add_all([
        CalendarBooking(
            id=uuid.uuid4(), calendar_id=cal.id, guest_name="Future",
            guest_email="f@example.com",
            start_time=now + timedelta(hours=1), end_time=now + timedelta(hours=2),
            status=BookingStatus.CONFIRMED,
        ),
        CalendarBooking(
            id=uuid.uuid4(), calendar_id=cal.id, guest_name="Cancelled",
            guest_email="c@example.com",
            start_time=now - timedelta(hours=2), end_time=now - timedelta(hours=1),
            status=BookingStatus.CANCELLED,
        ),
    ])
    await db.commit()

    assert await complete_past_bookings(db, now=now) == 0


# ── SCHEDULED ────────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_scheduled_workflow_runs_on_interval(db: AsyncSession, admin_user: User):
    from app.workflows.service import run_scheduled_workflows

    wf = await _make_workflow(
        db, admin_user, TriggerType.SCHEDULED, {"interval_minutes": 60}
    )

    # Never run before → due immediately.
    assert await run_scheduled_workflows(db) == 1
    assert await _executions(db, wf) == 1

    # Running again straight away must NOT double-fire.
    assert await run_scheduled_workflows(db) == 0
    assert await _executions(db, wf) == 1


@pytest.mark.normal
async def test_scheduled_due_matcher():
    from app.workflows.service import _due

    now = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)

    # Interval: due when never run, and after the interval elapses.
    assert _due({"interval_minutes": 60}, now, None) is True
    assert _due({"interval_minutes": 60}, now, now - timedelta(minutes=30)) is False
    assert _due({"interval_minutes": 60}, now, now - timedelta(minutes=90)) is True

    # Daily cron at the matching hour only.
    assert _due({"cron": {"hour": 9, "minute": 0}}, now, None) is True
    assert _due({"cron": {"hour": 17, "minute": 0}}, now, None) is False

    # Weekday / day-of-month narrowing (2026-07-24 is a Friday = weekday 4).
    assert _due({"cron": {"hour": 9, "weekday": 4}}, now, None) is True
    assert _due({"cron": {"hour": 9, "weekday": 0}}, now, None) is False
    assert _due({"cron": {"hour": 9, "day": 24}}, now, None) is True
    assert _due({"cron": {"hour": 9, "day": 1}}, now, None) is False

    # Junk config never fires.
    assert _due({}, now, None) is False
    assert _due({"interval_minutes": 0}, now, None) is False


@pytest.mark.normal
async def test_inactive_scheduled_workflow_does_not_run(
    db: AsyncSession, admin_user: User
):
    from app.workflows.service import run_scheduled_workflows

    wf = await _make_workflow(
        db, admin_user, TriggerType.SCHEDULED, {"interval_minutes": 60}
    )
    wf.is_active = False
    await db.commit()

    assert await run_scheduled_workflows(db) == 0


# ── WEBHOOK_RECEIVED ─────────────────────────────────────────────────────


@pytest.mark.critical
async def test_inbound_webhook_fires_its_workflow(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    from app.workflows.service import ensure_webhook_key

    wf = await _make_workflow(db, admin_user, TriggerType.WEBHOOK_RECEIVED)
    key = await ensure_webhook_key(db, wf)

    resp = await client.post(
        f"/api/workflows/webhook/{key}", json={"lead": "Acme", "value": 100}
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["data"]["triggered"] is True
    assert await _executions(db, wf) == 1


@pytest.mark.normal
async def test_unknown_webhook_key_is_accepted_but_fires_nothing(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """202 either way so a caller can't probe which keys exist."""
    wf = await _make_workflow(db, admin_user, TriggerType.WEBHOOK_RECEIVED)

    resp = await client.post("/api/workflows/webhook/not-a-real-key", json={})
    assert resp.status_code == 202
    assert resp.json()["data"]["triggered"] is False
    assert await _executions(db, wf) == 0


@pytest.mark.normal
async def test_webhook_key_isolates_workflows(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """One workflow's key must never run another's — the key identifies one."""
    from app.workflows.service import ensure_webhook_key

    wf_a = await _make_workflow(db, admin_user, TriggerType.WEBHOOK_RECEIVED)
    wf_b = await _make_workflow(db, admin_user, TriggerType.WEBHOOK_RECEIVED)
    key_a = await ensure_webhook_key(db, wf_a)
    await ensure_webhook_key(db, wf_b)

    await client.post(f"/api/workflows/webhook/{key_a}", json={})
    assert await _executions(db, wf_a) == 1
    assert await _executions(db, wf_b) == 0


@pytest.mark.normal
async def test_rotating_webhook_key_revokes_the_old_url(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    from app.workflows.service import ensure_webhook_key

    wf = await _make_workflow(db, admin_user, TriggerType.WEBHOOK_RECEIVED)
    old = await ensure_webhook_key(db, wf)
    new = await ensure_webhook_key(db, wf, rotate=True)
    assert old != new

    resp = await client.post(f"/api/workflows/webhook/{old}", json={})
    assert resp.json()["data"]["triggered"] is False
    assert await _executions(db, wf) == 0


# ── EMAIL_OPENED ─────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_email_open_pixel_fires_trigger_once(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    from app.email.models import EmailOpen

    wf = await _make_workflow(db, admin_user, TriggerType.EMAIL_OPENED)
    token = uuid.uuid4().hex
    db.add(EmailOpen(id=uuid.uuid4(), token=token, to_email="who@example.com", kind="invoice"))
    await db.commit()

    resp = await client.get(f"/api/email/track/open/{token}.gif")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"
    assert await _executions(db, wf) == 1

    # A second open counts, but must not re-fire the automation.
    resp2 = await client.get(f"/api/email/track/open/{token}.gif")
    assert resp2.status_code == 200
    assert await _executions(db, wf) == 1

    row = (await db.execute(select(EmailOpen).where(EmailOpen.token == token))).scalar_one()
    assert row.open_count == 2
    assert row.opened_at is not None


@pytest.mark.normal
async def test_unknown_open_token_still_returns_a_pixel(client: AsyncClient):
    """A broken token must never render a broken image in someone's inbox."""
    resp = await client.get("/api/email/track/open/nope.gif")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"


# ── PIPELINE_STAGE_CHANGED ───────────────────────────────────────────────


@pytest.mark.critical
async def test_pipeline_stage_change_fires(
    db: AsyncSession, admin_user: User, sample_contact
):
    """The Pipelines board is proposal status, so a status move is a stage move."""
    from app.proposals.models import Proposal, ProposalStatus
    from app.proposals.service import dispatch_stage_changed

    wf = await _make_workflow(db, admin_user, TriggerType.PIPELINE_STAGE_CHANGED)

    proposal = Proposal(
        id=uuid.uuid4(),
        proposal_number=f"PROP-{uuid.uuid4().hex[:6]}",
        contact_id=sample_contact.id,
        title="Test proposal",
        content_json="[]",
        value=100,
        status=ProposalStatus.SENT,
        created_by=admin_user.id,
    )
    db.add(proposal)
    await db.commit()

    await dispatch_stage_changed(db, proposal, ProposalStatus.DRAFT)
    assert await _executions(db, wf) == 1


@pytest.mark.normal
async def test_no_stage_change_when_status_unchanged(
    db: AsyncSession, admin_user: User, sample_contact
):
    from app.proposals.models import Proposal, ProposalStatus
    from app.proposals.service import dispatch_stage_changed

    wf = await _make_workflow(db, admin_user, TriggerType.PIPELINE_STAGE_CHANGED)
    proposal = Proposal(
        id=uuid.uuid4(),
        proposal_number=f"PROP-{uuid.uuid4().hex[:6]}",
        contact_id=sample_contact.id,
        title="Same status",
        content_json="[]",
        value=50,
        status=ProposalStatus.SENT,
        created_by=admin_user.id,
    )
    db.add(proposal)
    await db.commit()

    await dispatch_stage_changed(db, proposal, ProposalStatus.SENT)
    assert await _executions(db, wf) == 0
