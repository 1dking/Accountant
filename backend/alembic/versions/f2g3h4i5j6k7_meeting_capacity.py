"""Meeting capacity — max_participants + recording_layout (Commit 19)

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2g3h4i5j6k7"
down_revision: Union[str, None] = "e1f2g3h4i5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("max_participants", sa.Integer(), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("recording_layout", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meetings", "recording_layout")
    op.drop_column("meetings", "max_participants")
