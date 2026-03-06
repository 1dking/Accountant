
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.workflows.models import ActionType, ExecutionStatus, TriggerType


# ---------------------------------------------------------------------------
# Step schemas
# ---------------------------------------------------------------------------


class WorkflowStepCreate(BaseModel):
    step_order: int = Field(ge=0)
    action_type: ActionType
    action_config_json: Optional[str] = None
    condition_json: Optional[str] = None
    wait_duration_seconds: Optional[int] = Field(None, ge=0)


class WorkflowStepResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    step_order: int
    action_type: ActionType
    action_config_json: Optional[str]
    condition_json: Optional[str]
    wait_duration_seconds: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Workflow schemas
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: TriggerType
    trigger_config_json: Optional[str] = None
    steps: list[WorkflowStepCreate] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    trigger_config_json: Optional[str] = None
    is_active: Optional[bool] = None
    steps: Optional[list[WorkflowStepCreate]] = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    trigger_type: TriggerType
    trigger_config_json: Optional[str]
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    trigger_type: TriggerType
    is_active: bool
    created_at: datetime
    execution_count: int = 0
    last_run_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Execution schemas
# ---------------------------------------------------------------------------


class WorkflowExecutionStepResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    step_id: Optional[uuid.UUID]
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime]
    result_json: Optional[str]
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class WorkflowExecutionResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    steps: list[WorkflowExecutionStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dispatch schema
# ---------------------------------------------------------------------------


class DispatchEventRequest(BaseModel):
    event_type: TriggerType
    contact_id: Optional[uuid.UUID] = None
    event_data: Optional[dict] = None


class ToggleRequest(BaseModel):
    is_active: bool
