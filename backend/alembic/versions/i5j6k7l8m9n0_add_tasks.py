"""Add tasks table

The contact "Tasks" tab was a placeholder and the workflow engine's CREATE_TASK
action had no table to write to, because no task model existed anywhere.

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Nullable: a task can stand alone, not tied to a contact.
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("TODO", "IN_PROGRESS", "DONE", "CANCELLED", name="taskstatus"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="taskpriority"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # Deleting a contact takes its tasks with it; deleting a user leaves
        # their tasks in place but unassigned, so work isn't lost with the seat.
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_contact_id", "tasks", ["contact_id"])
    op.create_index("ix_tasks_assigned_user_id", "tasks", ["assigned_user_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_assigned_user_id", table_name="tasks")
    op.drop_index("ix_tasks_contact_id", table_name="tasks")
    op.drop_table("tasks")
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="taskpriority").drop(op.get_bind(), checkfirst=True)
