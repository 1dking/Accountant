"""Coach intelligence tables

Revision ID: b2c3d4e5f6a7
Revises: a1ac587a8fea
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1ac587a8fea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("_dummy_coach", recreate="never", naming_convention=None) if False else _noop():
        pass

    op.create_table(
        "meeting_intelligence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("topics_json", sa.Text(), nullable=True),
        sa.Column("action_items_json", sa.Text(), nullable=True),
        sa.Column("decisions_json", sa.Text(), nullable=True),
        sa.Column("sentiment_json", sa.Text(), nullable=True),
        sa.Column("talk_ratio_json", sa.Text(), nullable=True),
        sa.Column("deal_signals_json", sa.Text(), nullable=True),
        sa.Column("risk_flags_json", sa.Text(), nullable=True),
        sa.Column("follow_ups_json", sa.Text(), nullable=True),
        sa.Column("suggestions_json", sa.Text(), nullable=True),
        sa.Column("action_items_completed_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_intelligence_meeting_id", "meeting_intelligence", ["meeting_id"], unique=True)

    op.create_table(
        "monthly_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("report_month", sa.String(7), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("whats_working_json", sa.Text(), nullable=True),
        sa.Column("watch_out_json", sa.Text(), nullable=True),
        sa.Column("revenue_insights_json", sa.Text(), nullable=True),
        sa.Column("meeting_patterns_json", sa.Text(), nullable=True),
        sa.Column("recommendations_json", sa.Text(), nullable=True),
        sa.Column("trend_data_json", sa.Text(), nullable=True),
        sa.Column("win_loss_json", sa.Text(), nullable=True),
        sa.Column("health_score", sa.Integer(), server_default="50", nullable=False),
        sa.Column("raw_data_json", sa.Text(), nullable=True),
        sa.Column("team_data_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deal_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("deal_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("cycle_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("meetings_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("emails_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("win_factors_json", sa.Text(), nullable=True),
        sa.Column("loss_factors_json", sa.Text(), nullable=True),
        sa.Column("analysis_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "coaching_nudges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("nudge_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("is_acted_on", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coaching_nudges_user_id", "coaching_nudges", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_coaching_nudges_user_id", table_name="coaching_nudges")
    op.drop_table("coaching_nudges")
    op.drop_table("deal_outcomes")
    op.drop_table("monthly_reports")
    op.drop_index("ix_meeting_intelligence_meeting_id", table_name="meeting_intelligence")
    op.drop_table("meeting_intelligence")


def _noop():
    """No-op context manager to avoid syntax issues."""
    from contextlib import contextmanager
    @contextmanager
    def noop():
        yield
    return noop()
