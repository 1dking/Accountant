"""Add organizations, org feature/setting overrides, users.org_id

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- organizations table --
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("plan", sa.String(length=50), server_default="starter", nullable=False),
        sa.Column("max_users", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_storage_gb", sa.Integer(), server_default="5", nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("secondary_color", sa.String(length=7), nullable=True),
        sa.Column("custom_domain", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_organizations_slug"), ["slug"], unique=True)

    # -- org_feature_overrides table --
    op.create_table(
        "org_feature_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "feature_key", name="uq_org_feature_key"),
    )
    with op.batch_alter_table("org_feature_overrides", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_org_feature_overrides_org_id"), ["org_id"], unique=False)

    # -- org_setting_overrides table --
    op.create_table(
        "org_setting_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "setting_key", name="uq_org_setting_key"),
    )
    with op.batch_alter_table("org_setting_overrides", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_org_setting_overrides_org_id"), ["org_id"], unique=False)

    # -- Add org_id to users --
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_org_id", "organizations", ["org_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index(batch_op.f("ix_users_org_id"), ["org_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_org_id"))
        batch_op.drop_constraint("fk_users_org_id", type_="foreignkey")
        batch_op.drop_column("org_id")

    with op.batch_alter_table("org_setting_overrides", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_org_setting_overrides_org_id"))
    op.drop_table("org_setting_overrides")

    with op.batch_alter_table("org_feature_overrides", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_org_feature_overrides_org_id"))
    op.drop_table("org_feature_overrides")

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_organizations_slug"))
    op.drop_table("organizations")
