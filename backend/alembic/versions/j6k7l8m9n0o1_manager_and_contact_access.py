"""Add manager_id + contact_access (explicit contact sharing)

Records are private to their owner. This adds the two things that make that
liveable: a MANAGER who can see their direct reports, and an explicit grant of
one contact to one colleague.

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # Who each employee reports to. Nullable — most people report to nobody.
    # SET NULL, not CASCADE: removing a manager must not delete their reports.
    op.add_column("users", sa.Column("manager_id", sa.Uuid(), nullable=True))
    op.create_index("ix_users_manager_id", "users", ["manager_id"])

    # The FK is only created on Postgres. SQLite has no ALTER TABLE ADD
    # CONSTRAINT at all — alembic's SQLite dialect raises outright — and the only
    # workaround is batch mode, which rebuilds the entire `users` table by
    # copy-and-move. Rebuilding the live accounts table to gain a constraint
    # SQLite does not enforce by default (PRAGMA foreign_keys is off) is a bad
    # trade. The relationship is declared on the model, so the ORM behaves
    # identically either way, and a fresh SQLite DB built by create_all() gets the
    # constraint inline at CREATE TABLE.
    if not is_sqlite:
        op.create_foreign_key(
            "fk_users_manager_id",
            "users",
            "users",
            ["manager_id"],
            ["id"],
            ondelete="SET NULL",
        )
        # Postgres pins enum values in a type; SQLite stores role as a plain
        # VARCHAR (Enum is mapped with create_constraint=False), so it needs no
        # DDL to accept 'manager'.
        op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'MANAGER'")

    # No DDL is needed to add MANAGER to the role enum on SQLite: the Enum is
    # mapped with create_constraint=False, so users.role is a plain VARCHAR with
    # no CHECK. Postgres would need ALTER TYPE ... ADD VALUE.

    op.create_table(
        "contact_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "permission",
            sa.Enum("VIEW", "EDIT", name="sharepermission"),
            nullable=False,
        ),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Re-sharing to the same person is an UPSERT of the permission, not a
        # second row.
        sa.UniqueConstraint("contact_id", "user_id", name="uq_contact_access"),
    )
    op.create_index("ix_contact_access_contact_id", "contact_access", ["contact_id"])
    op.create_index("ix_contact_access_user_id", "contact_access", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_index("ix_contact_access_user_id", table_name="contact_access")
    op.drop_index("ix_contact_access_contact_id", table_name="contact_access")
    op.drop_table("contact_access")
    sa.Enum(name="sharepermission").drop(bind, checkfirst=True)

    if not is_sqlite:
        op.drop_constraint("fk_users_manager_id", "users", type_="foreignkey")
    op.drop_index("ix_users_manager_id", table_name="users")
    op.drop_column("users", "manager_id")
