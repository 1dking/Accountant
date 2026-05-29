"""Meeting template (Commit 16 — discovery / internal / review presets)

Revision ID: e1f2g3h4i5j6
Revises: d0e1f2g3h4i5
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2g3h4i5j6"
down_revision: Union[str, None] = "d0e1f2g3h4i5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column(
            "template", sa.String(32),
            nullable=False, server_default="generic",
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "template")
