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
    # SQLite has no ALTER TABLE ADD CONSTRAINT — Alembic's sqlite dialect
    # raises NotImplementedError on a plain create_foreign_key/create_index
    # here and requires batch mode (copy-and-move table rebuild) instead.
    with op.batch_alter_table("page_templates") as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_page_templates_org_id",
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_page_templates_org_id", ["org_id"])

    op.execute("""
        UPDATE page_templates
        SET org_id = (
            SELECT u.org_id FROM users u
            WHERE u.id = page_templates.created_by
              AND u.org_id IS NOT NULL
        )
        WHERE created_by IN (
            SELECT u.id FROM users u WHERE u.org_id IS NOT NULL
        )
    """)


def downgrade() -> None:
    with op.batch_alter_table("page_templates") as batch_op:
        batch_op.drop_index("ix_page_templates_org_id")
        batch_op.drop_constraint("fk_page_templates_org_id", type_="foreignkey")
        batch_op.drop_column("org_id")
