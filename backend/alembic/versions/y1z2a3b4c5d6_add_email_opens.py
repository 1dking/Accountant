"""Add email_opens table (open tracking -> EMAIL_OPENED workflow trigger)

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3b4c5
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y1z2a3b4c5d6"
down_revision: Union[str, None] = "x0y1z2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_opens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("to_email", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token", name="uq_email_opens_token"),
    )
    op.create_index("ix_email_opens_token", "email_opens", ["token"])
    op.create_index("ix_email_opens_contact_id", "email_opens", ["contact_id"])


def downgrade() -> None:
    op.drop_index("ix_email_opens_contact_id", table_name="email_opens")
    op.drop_index("ix_email_opens_token", table_name="email_opens")
    op.drop_table("email_opens")
