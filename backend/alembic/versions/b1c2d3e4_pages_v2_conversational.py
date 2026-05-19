"""Add page_generation_sessions table + pages.generation_session_id

Revision ID: b1c2d3e4
Revises: z6a7b8c9d0e1
Create Date: 2026-05-19

Pages v2 — conversational PRD-first generation flow. A session
captures the multi-turn conversation that produces a PRD, the user's
approval, the generation status, and (after generation) links to the
page row produced from it. Inspired by the Tempo Labs / Lovable
PRD-first pattern.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4"
down_revision: Union[str, None] = "z6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_generation_sessions",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Set ONCE the session generates a page. Until then a session
        # is a conversation without a target row. Nullable + indexed so
        # we can quickly look up the session for a given page during
        # refine flows.
        sa.Column("page_id", sa.CHAR(32), nullable=True),
        # Multi-turn prompt history: [{role, content, timestamp}]
        sa.Column("prompt_history", sa.JSON, nullable=False, server_default="[]"),
        # Structured PRD that Claude produces from the prompt.
        # Schema: { title, audience, goals: [str], sections: [{id, type, title, summary, content_brief}] }
        sa.Column("prd", sa.JSON, nullable=True),
        # Sitemap is a flat list of section IDs in render order.
        # Distinct from prd because the user can reorder without
        # touching the PRD's section content briefs.
        sa.Column("sitemap", sa.JSON, nullable=True),
        # 'drafting' → user is still iterating on the prompt + PRD
        # 'approved' → user clicked Approve, generation queued
        # 'generating' → worker is producing section JSX
        # 'complete' → page row populated, session done
        # 'failed' → worker raised; error_message has the details
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="drafting",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        "ix_page_generation_sessions_user_status",
        "page_generation_sessions",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_page_generation_sessions_page",
        "page_generation_sessions",
        ["page_id"],
    )

    # Link a generated page back to the session that produced it.
    # Logical FK only — SQLite ALTER ADD FOREIGN KEY is the same
    # limitation as identity_capture / absorbed_emails (deferred to
    # the application layer).
    op.add_column(
        "pages",
        sa.Column("generation_session_id", sa.CHAR(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pages", "generation_session_id")
    op.drop_index(
        "ix_page_generation_sessions_page",
        table_name="page_generation_sessions",
    )
    op.drop_index(
        "ix_page_generation_sessions_user_status",
        table_name="page_generation_sessions",
    )
    op.drop_table("page_generation_sessions")
