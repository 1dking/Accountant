"""Add email absorption tables + columns

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z6a7b8c9d0e1"
down_revision: Union[str, None] = "y5z6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-contact opt-out — default true so existing contacts are
    # eligible without backfilling the column.
    op.add_column(
        "contacts",
        sa.Column(
            "email_absorption_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # Cursor for incremental absorption. NULL → next run does a 90-day
    # backfill; populated after first run so subsequent scans only
    # cover the recent delta (with a 1-day overlap for safety).
    op.add_column(
        "gmail_accounts",
        sa.Column(
            "absorption_last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # absorbed_emails — one row per Gmail message we matched + summarized
    # for a contact. Idempotency anchor is (user_id, gmail_message_id).
    # memory_id is logical FK; SQLite ALTER constraint limits prevent
    # adding it as a hard FK after the fact, but the application
    # enforces existence.
    op.create_table(
        "absorbed_emails",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.CHAR(32),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_summary", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "absorbed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("memory_id", sa.CHAR(32), nullable=True),
    )
    op.create_index(
        "ix_absorbed_emails_user_gmail_id",
        "absorbed_emails",
        ["user_id", "gmail_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_absorbed_emails_contact_sent",
        "absorbed_emails",
        ["contact_id", "sent_at"],
    )
    op.create_index(
        "ix_absorbed_emails_thread",
        "absorbed_emails",
        ["thread_id"],
    )

    # email_absorption_runs — tracks each absorb invocation so the
    # frontend can poll for status. created_at is NOT NULL so the
    # "list recent runs" query has a stable sort key even before
    # started_at is populated.
    op.create_table(
        "email_absorption_runs",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("absorbed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contacts_touched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_email_absorption_runs_user_created",
        "email_absorption_runs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_absorption_runs_user_created", table_name="email_absorption_runs")
    op.drop_table("email_absorption_runs")

    op.drop_index("ix_absorbed_emails_thread", table_name="absorbed_emails")
    op.drop_index("ix_absorbed_emails_contact_sent", table_name="absorbed_emails")
    op.drop_index("ix_absorbed_emails_user_gmail_id", table_name="absorbed_emails")
    op.drop_table("absorbed_emails")

    op.drop_column("gmail_accounts", "absorption_last_run_at")
    op.drop_column("contacts", "email_absorption_enabled")
