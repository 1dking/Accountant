from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role
from app.recurring import service
from app.recurring.schemas import (
    RecurringRuleCreate,
    RecurringRuleListItem,
    RecurringRuleResponse,
    RecurringRuleUpdate,
)

router = APIRouter()


def _to_response(rule) -> dict:
    """Convert rule to response dict, parsing template_data JSON."""
    data = RecurringRuleListItem.model_validate(rule).model_dump()
    data["template_data"] = json.loads(rule.template_data)
    return data


@router.get("")
async def list_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    rules, meta = await service.list_rules(db, pagination)
    return {
        "data": [_to_response(r) for r in rules],
        "meta": meta,
    }


@router.get("/upcoming")
async def upcoming_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    rules = await service.get_upcoming_rules(db)
    return {"data": [_to_response(r) for r in rules]}


@router.post("", status_code=201)
async def create_rule(
    data: RecurringRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    rule = await service.create_rule(db, data, current_user)
    resp = RecurringRuleResponse.model_validate(rule).model_dump()
    resp["template_data"] = json.loads(rule.template_data)
    return {"data": resp}


@router.get("/{rule_id}")
async def get_rule(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    rule = await service.get_rule(db, rule_id)
    resp = RecurringRuleResponse.model_validate(rule).model_dump()
    resp["template_data"] = json.loads(rule.template_data)
    return {"data": resp}


@router.put("/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    data: RecurringRuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    rule = await service.update_rule(db, rule_id, data, current_user)
    resp = RecurringRuleResponse.model_validate(rule).model_dump()
    resp["template_data"] = json.loads(rule.template_data)
    return {"data": resp}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_rule(db, rule_id)
    return {"data": {"message": "Recurring rule deleted"}}


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    rule = await service.toggle_rule(db, rule_id)
    resp = RecurringRuleResponse.model_validate(rule).model_dump()
    resp["template_data"] = json.loads(rule.template_data)
    return {"data": resp}


@router.post("/process")
async def process_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    count = await service.process_recurring_rules(db)
    return {"data": {"processed": count}}
