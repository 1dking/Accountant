
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role
from app.invoicing import reminder_service
from app.invoicing.reminder_schemas import (
    ManualReminderRequest,
    PaymentReminderResponse,
    ReminderRuleCreate,
    ReminderRuleResponse,
    ReminderRuleUpdate,
)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Reminder Rules CRUD
# ---------------------------------------------------------------------------


@router.get("/reminder-rules")
async def list_reminder_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    rules = await reminder_service.list_reminder_rules(db)
    return {"data": [ReminderRuleResponse.model_validate(r) for r in rules]}


@router.post("/reminder-rules", status_code=201)
async def create_reminder_rule(
    data: ReminderRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    rule = await reminder_service.create_reminder_rule(db, data, current_user)
    return {"data": ReminderRuleResponse.model_validate(rule)}


@router.put("/reminder-rules/{rule_id}")
async def update_reminder_rule(
    rule_id: uuid.UUID,
    data: ReminderRuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    rule = await reminder_service.update_reminder_rule(db, rule_id, data)
    return {"data": ReminderRuleResponse.model_validate(rule)}


@router.delete("/reminder-rules/{rule_id}")
async def delete_reminder_rule(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await reminder_service.delete_reminder_rule(db, rule_id)
    return {"data": {"message": "Reminder rule deleted"}}


# ---------------------------------------------------------------------------
# Reminder History & Manual Send
# ---------------------------------------------------------------------------


@router.get("/{invoice_id}/reminders")
async def get_reminder_history(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    reminders = await reminder_service.get_reminder_history(db, invoice_id)
    return {"data": [PaymentReminderResponse.model_validate(r) for r in reminders]}


@router.post("/{invoice_id}/send-reminder", status_code=201)
async def send_manual_reminder(
    invoice_id: uuid.UUID,
    data: ManualReminderRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    settings = _get_settings(request)
    reminder = await reminder_service.send_manual_reminder(
        db, invoice_id, data, current_user, settings,
    )
    return {"data": PaymentReminderResponse.model_validate(reminder)}
