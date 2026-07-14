"""Business logic for tasks."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.authorization import apply_visibility_filter, authorize_record
from app.core.exceptions import NotFoundError
from app.tasks.models import Task, TaskStatus
from app.tasks.schemas import TaskCreate, TaskUpdate


async def get_task(db: AsyncSession, task_id: uuid.UUID, user: User) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise NotFoundError("Task", str(task_id))
    await authorize_record(
        db, user, task.created_by, contact_id=task.contact_id, resource_name="Task"
    )
    return task


async def list_tasks(
    db: AsyncSession,
    user: User,
    contact_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    """Open work first, then by due date — an undated task shouldn't outrank
    one that's due tomorrow, so nulls sort last."""
    query = select(Task)
    query = apply_visibility_filter(query, Task.created_by, user, contact_col=Task.contact_id)

    if contact_id is not None:
        query = query.where(Task.contact_id == contact_id)
    if status is not None:
        query = query.where(Task.status == status)

    query = query.order_by(
        Task.due_date.is_(None),
        Task.due_date.asc(),
        Task.created_at.desc(),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_task(db: AsyncSession, data: TaskCreate, user: User) -> Task:
    task = Task(
        id=uuid.uuid4(),
        title=data.title,
        description=data.description,
        contact_id=data.contact_id,
        assigned_user_id=data.assigned_user_id,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        created_by=user.id,
    )
    if task.status == TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc)

    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession, task_id: uuid.UUID, data: TaskUpdate, user: User
) -> Task:
    task = await get_task(db, task_id, user)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(task, field, value)

    # completed_at tracks the DONE transition in both directions — reopening a
    # task must clear it, or the timeline shows a completion that was undone.
    if "status" in updates:
        if task.status == TaskStatus.DONE and task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
        elif task.status != TaskStatus.DONE:
            task.completed_at = None

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID, user: User) -> None:
    task = await get_task(db, task_id, user)
    await db.delete(task)
    await db.commit()
