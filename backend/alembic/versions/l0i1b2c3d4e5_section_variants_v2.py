"""Block model v2 — dynamic blocks (fields schema, data binding, behaviour, motion, locale copy)

Revision ID: l0i1b2c3d4e5
Revises: k9h0a1b2c3d4
Create Date: 2026-09-07

All columns nullable / defaulted so the 18 v1 seeds keep working untouched.
SQLite dev DBs get the same columns from core/schema_patch.py (additive ALTERs
at boot); this migration is the Postgres path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l0i1b2c3d4e5"
down_revision: Union[str, None] = "k9h0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("section_variants") as b:
        b.add_column(sa.Column("fields_schema", sa.JSON(), nullable=True))
        b.add_column(sa.Column("data_source", sa.String(32), nullable=True))
        b.add_column(sa.Column("data_mode", sa.String(16), nullable=True))
        b.add_column(sa.Column("behaviour", sa.String(64), nullable=True))
        b.add_column(sa.Column("capabilities", sa.JSON(), nullable=True))
        b.add_column(sa.Column("motion_preset", sa.String(64), nullable=True))
        b.add_column(sa.Column("locale_props", sa.JSON(), nullable=True))
        b.add_column(sa.Column("thumbnail_hash", sa.String(64), nullable=True))
        b.add_column(sa.Column("thumbnail_rendered_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("section_variants") as b:
        for col in (
            "schema_version", "thumbnail_rendered_at", "thumbnail_hash", "locale_props",
            "motion_preset", "capabilities", "behaviour", "data_mode", "data_source",
            "fields_schema",
        ):
            b.drop_column(col)
