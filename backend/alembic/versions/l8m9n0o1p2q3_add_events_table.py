"""add events table

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-07-19 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8m9n0o1p2q3"
down_revision: Union[str, None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("properties_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_events_dedupe_key"),
    )
    op.create_index("ix_events_event", "events", ["event"])
    op.create_index("ix_events_org_id", "events", ["org_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_dedupe_key", "events", ["dedupe_key"])


def downgrade() -> None:
    op.drop_index("ix_events_dedupe_key", table_name="events")
    op.drop_index("ix_events_timestamp", table_name="events")
    op.drop_index("ix_events_org_id", table_name="events")
    op.drop_index("ix_events_event", table_name="events")
    op.drop_table("events")
