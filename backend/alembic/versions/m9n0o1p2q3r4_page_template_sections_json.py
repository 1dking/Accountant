"""Add sections_json to page_templates

Templates built from a page previously lost the structured section data,
leaving cloned pages editable only as raw HTML/CSS. This snapshots the
source page's sections_json so create_page_from_template can restore it.

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, None] = "l8m9n0o1p2q3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("page_templates", sa.Column("sections_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("page_templates", "sections_json")
