"""Add org_id to page_templates for tenant-scoped ORG templates

ORG-scoped templates were visible to every tenant on the shared deployment
because list_templates never filtered by org. Mirrors CashbookEntry.org_id /
PaymentAccount.org_id (see apply_cashbook_filter in app/core/authorization.py)
and its migration i9j0k1l2m3n4_org_cashbook_access.py, including the backfill
of existing rows from their creator's org_id.

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("page_templates", sa.Column("org_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_page_templates_org_id",
        "page_templates",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_page_templates_org_id", "page_templates", ["org_id"])

    op.execute("""
        UPDATE page_templates
        SET org_id = u.org_id
        FROM users u
        WHERE page_templates.created_by = u.id
          AND u.org_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_page_templates_org_id", table_name="page_templates")
    op.drop_constraint("fk_page_templates_org_id", "page_templates", type_="foreignkey")
    op.drop_column("page_templates", "org_id")
