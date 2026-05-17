"""Extend notifications table with link_path + contact_id

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-05-17

The notifications table already exists (push notifications + basic CRUD).
This migration adds the two fields needed for inline-navigable in-app
notifications: link_path (frontend route to navigate on click) and
contact_id (for direct contact-detail navigation + filtering).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("link_path", sa.String(length=500), nullable=True),
    )
    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so this column
    # is a plain CHAR(32) without FK enforcement. App-level validation
    # handles integrity (existing pattern — see e.g. CallLog.source_id
    # in voicemail flow).
    op.add_column(
        "notifications",
        sa.Column("contact_id", sa.CHAR(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "contact_id")
    op.drop_column("notifications", "link_path")
