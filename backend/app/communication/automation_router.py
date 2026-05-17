"""CRUD endpoints for user-managed SMS automation flows."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.communication.models import SmsAutomationFlow, SmsAutomationStep
from app.dependencies import get_current_user, get_db

router = APIRouter()

VALID_TRIGGERS = {"missed_call", "voicemail", "inbound_sms_unknown"}
MAX_STEPS = 10
MAX_STEP_BODY = 320  # 2 SMS segments — caller can read but won't ramble
MAX_DELAY_MINUTES = 60 * 24 * 7  # 7 days


def _step_to_dict(step: SmsAutomationStep) -> dict:
    return {
        "id": str(step.id),
        "step_order": step.step_order,
        "message_body": step.message_body,
        "delay_minutes": step.delay_minutes,
        "include_booking_link": step.include_booking_link,
    }


def _flow_to_dict(flow: SmsAutomationFlow, steps: list[SmsAutomationStep]) -> dict:
    return {
        "id": str(flow.id),
        "user_id": str(flow.user_id),
        "name": flow.name,
        "trigger_type": flow.trigger_type,
        "is_active": flow.is_active,
        "created_at": flow.created_at.isoformat() if flow.created_at else None,
        "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
        "steps": [_step_to_dict(s) for s in steps],
    }


def _validate_steps(steps: list[dict]) -> None:
    if not steps:
        raise HTTPException(status_code=400, detail="At least one step required")
    if len(steps) > MAX_STEPS:
        raise HTTPException(
            status_code=400, detail=f"Maximum {MAX_STEPS} steps per flow"
        )
    orders = [s.get("step_order") for s in steps]
    if orders != sorted(orders) or len(set(orders)) != len(orders):
        raise HTTPException(
            status_code=400, detail="step_order must be unique and sequential"
        )
    for s in steps:
        body = (s.get("message_body") or "").strip()
        if not body:
            raise HTTPException(
                status_code=400,
                detail=f"step {s.get('step_order')}: message_body required",
            )
        if len(body) > MAX_STEP_BODY:
            raise HTTPException(
                status_code=400,
                detail=f"step {s.get('step_order')}: message_body exceeds {MAX_STEP_BODY} chars",
            )
        delay = s.get("delay_minutes", 0)
        if not isinstance(delay, int) or delay < 0 or delay > MAX_DELAY_MINUTES:
            raise HTTPException(
                status_code=400,
                detail=f"step {s.get('step_order')}: delay_minutes must be 0..{MAX_DELAY_MINUTES}",
            )


@router.get("/automation-flows")
async def list_flows(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    flows_result = await db.execute(
        select(SmsAutomationFlow)
        .where(SmsAutomationFlow.user_id == current_user.id)
        .order_by(SmsAutomationFlow.created_at.desc())
    )
    flows = list(flows_result.scalars().all())
    out = []
    for flow in flows:
        steps_result = await db.execute(
            select(SmsAutomationStep)
            .where(SmsAutomationStep.flow_id == flow.id)
            .order_by(SmsAutomationStep.step_order)
        )
        steps = list(steps_result.scalars().all())
        out.append(_flow_to_dict(flow, steps))
    return {"data": out}


@router.post("/automation-flows", status_code=201)
async def create_flow(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    name = (body.get("name") or "").strip()
    trigger_type = body.get("trigger_type")
    steps_in = body.get("steps") or []

    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="name exceeds 100 chars")
    if trigger_type not in VALID_TRIGGERS:
        raise HTTPException(
            status_code=400, detail=f"trigger_type must be one of: {sorted(VALID_TRIGGERS)}"
        )
    _validate_steps(steps_in)

    flow = SmsAutomationFlow(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=name,
        trigger_type=trigger_type,
        is_active=bool(body.get("is_active", True)),
    )
    db.add(flow)
    await db.flush()  # get the id without committing

    step_objs = []
    for s in steps_in:
        obj = SmsAutomationStep(
            id=uuid.uuid4(),
            flow_id=flow.id,
            step_order=int(s["step_order"]),
            message_body=s["message_body"].strip(),
            delay_minutes=int(s.get("delay_minutes", 0)),
            include_booking_link=bool(s.get("include_booking_link", False)),
        )
        step_objs.append(obj)
        db.add(obj)
    await db.commit()
    await db.refresh(flow)
    return {"data": _flow_to_dict(flow, step_objs)}


@router.put("/automation-flows/{flow_id}")
async def update_flow(
    flow_id: uuid.UUID,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Replace flow + steps. Step rows are deleted and re-created."""
    flow_result = await db.execute(
        select(SmsAutomationFlow).where(
            SmsAutomationFlow.id == flow_id,
            SmsAutomationFlow.user_id == current_user.id,
        )
    )
    flow = flow_result.scalar_one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")

    if "name" in body:
        name = (body["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        if len(name) > 100:
            raise HTTPException(status_code=400, detail="name exceeds 100 chars")
        flow.name = name
    if "trigger_type" in body:
        if body["trigger_type"] not in VALID_TRIGGERS:
            raise HTTPException(
                status_code=400,
                detail=f"trigger_type must be one of: {sorted(VALID_TRIGGERS)}",
            )
        flow.trigger_type = body["trigger_type"]
    if "is_active" in body:
        flow.is_active = bool(body["is_active"])

    if "steps" in body:
        steps_in = body["steps"] or []
        _validate_steps(steps_in)
        # Delete existing steps
        old_steps = await db.execute(
            select(SmsAutomationStep).where(SmsAutomationStep.flow_id == flow.id)
        )
        for old in list(old_steps.scalars().all()):
            await db.delete(old)
        await db.flush()
        # Add new steps
        for s in steps_in:
            obj = SmsAutomationStep(
                id=uuid.uuid4(),
                flow_id=flow.id,
                step_order=int(s["step_order"]),
                message_body=s["message_body"].strip(),
                delay_minutes=int(s.get("delay_minutes", 0)),
                include_booking_link=bool(s.get("include_booking_link", False)),
            )
            db.add(obj)

    await db.commit()

    steps_result = await db.execute(
        select(SmsAutomationStep)
        .where(SmsAutomationStep.flow_id == flow.id)
        .order_by(SmsAutomationStep.step_order)
    )
    steps = list(steps_result.scalars().all())
    return {"data": _flow_to_dict(flow, steps)}


@router.delete("/automation-flows/{flow_id}")
async def delete_flow(
    flow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    flow_result = await db.execute(
        select(SmsAutomationFlow).where(
            SmsAutomationFlow.id == flow_id,
            SmsAutomationFlow.user_id == current_user.id,
        )
    )
    flow = flow_result.scalar_one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    await db.delete(flow)
    await db.commit()
    return {"data": {"deleted": True}}


@router.post("/automation-flows/{flow_id}/toggle")
async def toggle_flow(
    flow_id: uuid.UUID,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    flow_result = await db.execute(
        select(SmsAutomationFlow).where(
            SmsAutomationFlow.id == flow_id,
            SmsAutomationFlow.user_id == current_user.id,
        )
    )
    flow = flow_result.scalar_one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow.is_active = bool(body.get("is_active", not flow.is_active))
    await db.commit()
    return {"data": {"id": str(flow.id), "is_active": flow.is_active}}
