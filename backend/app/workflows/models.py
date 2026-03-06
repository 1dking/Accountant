
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class TriggerType(str, enum.Enum):
    CONTACT_CREATED = "contact_created"
    CONTACT_TAG_ADDED = "contact_tag_added"
    CONTACT_TAG_REMOVED = "contact_tag_removed"
    FORM_SUBMITTED = "form_submitted"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_COMPLETED = "appointment_completed"
    INVOICE_CREATED = "invoice_created"
    INVOICE_SENT = "invoice_sent"
    INVOICE_PAID = "invoice_paid"
    INVOICE_OVERDUE = "invoice_overdue"
    PROPOSAL_SENT = "proposal_sent"
    PROPOSAL_VIEWED = "proposal_viewed"
    PROPOSAL_SIGNED = "proposal_signed"
    PROPOSAL_DECLINED = "proposal_declined"
    PAYMENT_RECEIVED = "payment_received"
    PIPELINE_STAGE_CHANGED = "pipeline_stage_changed"
    CALL_COMPLETED = "call_completed"
    SMS_RECEIVED = "sms_received"
    EMAIL_OPENED = "email_opened"
    SCHEDULED = "scheduled"
    WEBHOOK_RECEIVED = "webhook_received"


class ActionType(str, enum.Enum):
    SEND_EMAIL = "send_email"
    SEND_SMS = "send_sms"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    UPDATE_CONTACT_FIELD = "update_contact_field"
    CREATE_CONTACT = "create_contact"
    MOVE_PIPELINE_STAGE = "move_pipeline_stage"
    CREATE_TASK = "create_task"
    CREATE_NOTE = "create_note"
    CREATE_INVOICE = "create_invoice"
    SEND_PROPOSAL = "send_proposal"
    WAIT_DELAY = "wait_delay"
    IF_ELSE_BRANCH = "if_else_branch"
    WEBHOOK_OUTBOUND = "webhook_outbound"
    ADD_TO_WORKFLOW = "add_to_workflow"
    REMOVE_FROM_WORKFLOW = "remove_from_workflow"
    ASSIGN_TO_USER = "assign_to_user"
    SEND_NOTIFICATION = "send_notification"
    ASK_OBRAIN = "ask_obrain"
    LOG_TO_BRAIN = "log_to_brain"


class ExecutionStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"
    CANCELLED = "cancelled"


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), nullable=False)
    trigger_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    action_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    wait_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkflowExecutionStep(Base):
    __tablename__ = "workflow_execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
