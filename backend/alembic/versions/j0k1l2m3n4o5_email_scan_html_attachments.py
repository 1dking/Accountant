"""Add body_html and attachment_metadata to gmail_scan_results

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gmail_scan_results", sa.Column("body_html", sa.Text(), nullable=True))
    op.add_column("gmail_scan_results", sa.Column("attachment_metadata", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("gmail_scan_results", "attachment_metadata")
    op.drop_column("gmail_scan_results", "body_html")
