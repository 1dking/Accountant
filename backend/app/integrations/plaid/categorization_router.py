from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from fastapi import Request

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

from . import categorization_service as service
from .schemas import (
    CategorizationRuleCreate,
    CategorizationRuleResponse,
    CategorizationRuleUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Categorization Rules CRUD
# ---------------------------------------------------------------------------


@router.get("/categorization-rules", response_model=dict)
async def list_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rules = await service.list_rules(db)
    return {"data": [CategorizationRuleResponse.model_validate(r) for r in rules]}


@router.post("/categorization-rules", response_model=dict)
async def create_rule(
    data: CategorizationRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    rule = await service.create_rule(db, data, user)
    return {"data": CategorizationRuleResponse.model_validate(rule)}


@router.put("/categorization-rules/{rule_id}", response_model=dict)
async def update_rule(
    rule_id: uuid.UUID,
    data: CategorizationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    rule = await service.update_rule(db, rule_id, data)
    return {"data": CategorizationRuleResponse.model_validate(rule)}


@router.delete("/categorization-rules/{rule_id}", response_model=dict)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.delete_rule(db, rule_id)
    return {"data": {"detail": "Categorization rule deleted"}}


# ---------------------------------------------------------------------------
# Apply rules
# ---------------------------------------------------------------------------


@router.post("/apply-rules", response_model=dict)
async def apply_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    count = await service.apply_rules_to_all(db, user)
    return {"data": {"detail": f"Applied rules to {count} transaction(s)"}}


# ---------------------------------------------------------------------------
# AI categorization
# ---------------------------------------------------------------------------


@router.post("/ai-categorize", response_model=dict)
async def ai_categorize(
    request: "Request",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    """Use Claude AI to categorize uncategorized bank transactions."""
    from .ai_categorization import ai_categorize_transactions

    settings = request.app.state.settings
    count = await ai_categorize_transactions(db, str(user.id), settings)
    return {"data": {"detail": f"AI categorized {count} transaction(s)"}}
