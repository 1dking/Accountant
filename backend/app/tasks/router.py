import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.tasks import service
from app.tasks.models import TaskStatus
from app.tasks.schemas import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter()


@router.get("")
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    contact_id: uuid.UUID | None = Query(None),
    status: TaskStatus | None = Query(None),
) -> dict:
    tasks = await service.list_tasks(db, current_user, contact_id=contact_id, status=status)
    return {"data": [TaskResponse.model_validate(t) for t in tasks]}


@router.post("", status_code=201)
async def create_task(
    data: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))
    ],
) -> dict:
    task = await service.create_task(db, data, current_user)
    return {"data": TaskResponse.model_validate(task)}


@router.get("/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    task = await service.get_task(db, task_id, current_user)
    return {"data": TaskResponse.model_validate(task)}


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))
    ],
) -> dict:
    task = await service.update_task(db, task_id, data, current_user)
    return {"data": TaskResponse.model_validate(task)}


@router.delete("/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))
    ],
) -> dict:
    await service.delete_task(db, task_id, current_user)
    return {"data": {"message": "Task deleted"}}
