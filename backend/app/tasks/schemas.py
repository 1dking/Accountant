import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.tasks.models import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    contact_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    contact_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    contact_id: uuid.UUID | None
    assigned_user_id: uuid.UUID | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    completed_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
