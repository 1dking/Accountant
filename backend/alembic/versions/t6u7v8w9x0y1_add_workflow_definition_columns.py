"""Add definition_json and editor columns to workflows (canvas graph, Arivio port)

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t6u7v8w9x0y1"
down_revision: Union[str, None] = "s5t6u7v8w9x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("definition_json", sa.Text(), nullable=True))
    op.add_column(
        "workflows",
        sa.Column("editor", sa.String(length=20), nullable=False, server_default="steps"),
    )


def downgrade() -> None:
    op.drop_column("workflows", "editor")
    op.drop_column("workflows", "definition_json")
