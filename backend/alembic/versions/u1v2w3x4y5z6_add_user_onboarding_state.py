"""Add onboarding_state JSON column to users

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-05-17

onboarding_state stores per-item dismissal/timestamp metadata as a
JSON blob. Completion status itself is computed at runtime against
actual user data (has phone, has greeting, etc.) — not stored.
Structure: { item_key: { dismissed_at: ISO }, ... }
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_state",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_state")
