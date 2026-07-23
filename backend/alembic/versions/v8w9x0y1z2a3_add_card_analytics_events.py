"""Add card_analytics_events table (card view/save tracking)

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v8w9x0y1z2a3"
down_revision: Union[str, None] = "u7v8w9x0y1z2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("visitor_hash", sa.String(length=16), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["card_id"], ["business_cards.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_card_analytics_events_card_id", "card_analytics_events", ["card_id"])
    op.create_index("ix_card_analytics_events_event_type", "card_analytics_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_card_analytics_events_event_type", table_name="card_analytics_events")
    op.drop_index("ix_card_analytics_events_card_id", table_name="card_analytics_events")
    op.drop_table("card_analytics_events")
