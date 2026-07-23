"""Add CARD_VIEWED / CARD_CONTACT_SAVED to the triggertype enum

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-07-23

First-ever addition to an already-deployed native Postgres enum in this
repo. ALTER TYPE ... ADD VALUE cannot run inside a transaction, hence
autocommit_block. The enum stores Python member NAMES (uppercase), per
the original eef17b52e8a1 CREATE. SQLite (local dev/tests) stores enums
as VARCHAR via create_all — nothing to alter there.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "u7v8w9x0y1z2"
down_revision: Union[str, None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE triggertype ADD VALUE IF NOT EXISTS 'CARD_VIEWED'")
        op.execute("ALTER TYPE triggertype ADD VALUE IF NOT EXISTS 'CARD_CONTACT_SAVED'")


def downgrade() -> None:
    # Postgres can't drop enum values without a full type rebuild; an
    # unused trigger value is harmless, so this is deliberately a no-op.
    pass
