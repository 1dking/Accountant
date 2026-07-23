"""Add business_cards table (digital business card, Arivio port)

Revision ID: r4s5t6u7v8w9
Revises: o1p2q3r4s5t6
Create Date: 2026-07-22

Note: this originally pointed at q3r4s5t6u7v8, a revision that only
ever existed as an uncommitted local file (another session's WIP office-
comments migration) — never in git, never on the deploy target. That
broke the committed migration chain outright. Re-pointed at
o1p2q3r4s5t6 (Stripe Connect), the actual, already-deployed head.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r4s5t6u7v8w9"
down_revision: Union[str, None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("template", sa.String(length=20), nullable=False, server_default="classic"),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("social_links_json", sa.Text(), nullable=True),
        sa.Column("avatar_storage_path", sa.String(length=500), nullable=True),
        sa.Column("show_org_logo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("bg_color", sa.String(length=20), nullable=True),
        sa.Column("text_color", sa.String(length=20), nullable=True),
        sa.Column("accent_color", sa.String(length=20), nullable=True),
        sa.Column("button_color", sa.String(length=20), nullable=True),
        sa.Column("button_text_color", sa.String(length=20), nullable=True),
        sa.Column("font", sa.String(length=100), nullable=True),
        sa.Column("scheduling_calendar_id", sa.Uuid(), nullable=True),
        sa.Column("show_booking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["scheduling_calendar_id"], ["scheduling_calendars.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("user_id", name="uq_business_cards_user_id"),
        sa.UniqueConstraint("slug", name="uq_business_cards_slug"),
    )
    op.create_index("ix_business_cards_user_id", "business_cards", ["user_id"])
    op.create_index("ix_business_cards_slug", "business_cards", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_business_cards_slug", table_name="business_cards")
    op.drop_index("ix_business_cards_user_id", table_name="business_cards")
    op.drop_table("business_cards")
