"""Add contact_memories + sms_automation_flows + steps + booking_link

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 11B — Contact memory
    op.create_table(
        "contact_memories",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "contact_id",
            sa.CHAR(32),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_id", sa.CHAR(32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("commitments", sa.Text(), nullable=True),
        sa.Column("cares_about", sa.Text(), nullable=True),
        sa.Column("talking_points", sa.Text(), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_contact_memories_contact_created",
        "contact_memories",
        ["contact_id", "created_at"],
    )

    # Phase 11C — Multi-step SMS automation
    op.create_table(
        "sms_automation_flows",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sms_automation_flows_user_trigger",
        "sms_automation_flows",
        ["user_id", "trigger_type", "is_active"],
    )

    op.create_table(
        "sms_automation_steps",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "flow_id",
            sa.CHAR(32),
            sa.ForeignKey("sms_automation_flows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column(
            "delay_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "include_booking_link",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sms_automation_steps_flow_order",
        "sms_automation_steps",
        ["flow_id", "step_order"],
    )

    # New columns on existing tables
    op.add_column(
        "users",
        sa.Column("booking_link", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "call_logs",
        sa.Column(
            "automation_flow_triggered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("call_logs", "automation_flow_triggered_at")
    op.drop_column("users", "booking_link")
    op.drop_index("ix_sms_automation_steps_flow_order", table_name="sms_automation_steps")
    op.drop_table("sms_automation_steps")
    op.drop_index("ix_sms_automation_flows_user_trigger", table_name="sms_automation_flows")
    op.drop_table("sms_automation_flows")
    op.drop_index("ix_contact_memories_contact_created", table_name="contact_memories")
    op.drop_table("contact_memories")
