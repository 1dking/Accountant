
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.workflows import service
from app.workflows.schemas import (
    DispatchEventRequest,
    ToggleRequest,
    WorkflowCreate,
    WorkflowExecutionResponse,
    WorkflowExecutionStepResponse,
    WorkflowListItem,
    WorkflowResponse,
    WorkflowStepResponse,
    WorkflowUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Static paths first (before /{workflow_id})
# ---------------------------------------------------------------------------


@router.get("/templates")
async def list_templates(
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    """Return pre-built workflow templates as JSON."""
    return {"data": service.WORKFLOW_TEMPLATES}


@router.post("/dispatch")
async def dispatch_event(
    data: DispatchEventRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Manually dispatch an event (for testing). ADMIN only."""
    executions = await service.dispatch_event(
        db, data.event_type, data.event_data, data.contact_id
    )
    return {
        "data": {
            "dispatched_count": len(executions),
            "execution_ids": [str(e.id) for e in executions],
        }
    }


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_workflows(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    items, total = await service.list_workflows(db, page, page_size)
    return {
        "data": [WorkflowListItem(**item) for item in items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("", status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    workflow = await service.create_workflow(db, data, current_user)
    wf_data = await service.get_workflow(db, workflow.id)
    return {
        "data": WorkflowResponse(
            id=wf_data["workflow"].id,
            name=wf_data["workflow"].name,
            description=wf_data["workflow"].description,
            trigger_type=wf_data["workflow"].trigger_type,
            trigger_config_json=wf_data["workflow"].trigger_config_json,
            is_active=wf_data["workflow"].is_active,
            created_by=wf_data["workflow"].created_by,
            created_at=wf_data["workflow"].created_at,
            updated_at=wf_data["workflow"].updated_at,
            steps=[WorkflowStepResponse.model_validate(s) for s in wf_data["steps"]],
        )
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    wf_data = await service.get_workflow(db, workflow_id)
    return {
        "data": WorkflowResponse(
            id=wf_data["workflow"].id,
            name=wf_data["workflow"].name,
            description=wf_data["workflow"].description,
            trigger_type=wf_data["workflow"].trigger_type,
            trigger_config_json=wf_data["workflow"].trigger_config_json,
            is_active=wf_data["workflow"].is_active,
            created_by=wf_data["workflow"].created_by,
            created_at=wf_data["workflow"].created_at,
            updated_at=wf_data["workflow"].updated_at,
            steps=[WorkflowStepResponse.model_validate(s) for s in wf_data["steps"]],
        )
    }


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    workflow = await service.update_workflow(db, workflow_id, data, current_user)
    wf_data = await service.get_workflow(db, workflow.id)
    return {
        "data": WorkflowResponse(
            id=wf_data["workflow"].id,
            name=wf_data["workflow"].name,
            description=wf_data["workflow"].description,
            trigger_type=wf_data["workflow"].trigger_type,
            trigger_config_json=wf_data["workflow"].trigger_config_json,
            is_active=wf_data["workflow"].is_active,
            created_by=wf_data["workflow"].created_by,
            created_at=wf_data["workflow"].created_at,
            updated_at=wf_data["workflow"].updated_at,
            steps=[WorkflowStepResponse.model_validate(s) for s in wf_data["steps"]],
        )
    }


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_workflow(db, workflow_id)
    return {"data": {"message": "Workflow deleted"}}


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: uuid.UUID,
    data: ToggleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    workflow = await service.toggle_workflow(db, workflow_id, data.is_active)
    return {
        "data": {
            "id": str(workflow.id),
            "name": workflow.name,
            "is_active": workflow.is_active,
        }
    }


# ---------------------------------------------------------------------------
# Execution log
# ---------------------------------------------------------------------------


@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    items, total = await service.get_executions(db, workflow_id, page, page_size)
    executions = []
    for item in items:
        exec_steps = [
            WorkflowExecutionStepResponse(**s) for s in item["steps"]
        ]
        executions.append(
            WorkflowExecutionResponse(
                id=item["id"],
                workflow_id=item["workflow_id"],
                contact_id=item["contact_id"],
                status=item["status"],
                started_at=item["started_at"],
                completed_at=item["completed_at"],
                error_message=item["error_message"],
                steps=exec_steps,
            )
        )
    return {
        "data": executions,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }
