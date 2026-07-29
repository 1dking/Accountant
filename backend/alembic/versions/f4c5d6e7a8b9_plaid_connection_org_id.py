"""plaid connections: org_id for org-wide bank visibility

Adds a nullable ``org_id`` to ``plaid_connections`` so a bank connection can be
shared with an organization (org peers with org cashbook access see each other's
bank feed — the read filters reuse apply_cashbook_filter on user_id/org_id).
Backfills from each connection owner's current org. Managing a connection
(disconnect / force-sync / access-token decrypt) stays owner-only in code.

Revision ID: f4c5d6e7a8b9
Revises: f3b4c5d6e7a8
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op

revision = "f4c5d6e7a8b9"
down_revision = "f3b4c5d6e7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plaid_connections", sa.Column("org_id", sa.Uuid(), nullable=True))
    op.create_index("ix_plaid_connections_org_id", "plaid_connections", ["org_id"])
    op.create_foreign_key(
        "fk_plaid_connections_org_id",
        "plaid_connections",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Backfill each connection's org from its owner's current org.
    op.execute(
        "UPDATE plaid_connections SET org_id = "
        "(SELECT org_id FROM users WHERE users.id = plaid_connections.user_id) "
        "WHERE org_id IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_plaid_connections_org_id", "plaid_connections", type_="foreignkey")
    op.drop_index("ix_plaid_connections_org_id", table_name="plaid_connections")
    op.drop_column("plaid_connections", "org_id")
