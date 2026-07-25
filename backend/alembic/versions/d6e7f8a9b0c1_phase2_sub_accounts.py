"""Phase 2 — operator / sub-account primitive

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-24

Adds the sub_accounts + sub_account_features tables and the three tenancy columns
on users (sub_account_id, operator_id, is_platform_admin). All user columns are
nullable/defaulted so existing rows form one legacy tenant and behaviour is
unchanged until sub-accounts are provisioned.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS = sa.Enum("ACTIVE", "SUSPENDED", "ARCHIVED", name="subaccountstatus")
_MODE = sa.Enum("DOER", "RECIPIENT", name="dataentrymode")
_CRM = sa.Enum("FULL", "CLIENT_STYLE", name="crmstyle")
_TEMPLATE = sa.Enum("ACCOUNTING_PRACTICE", "MARKETING_AGENCY", "CUSTOM", name="onboardingtemplate")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for e in (_STATUS, _MODE, _CRM, _TEMPLATE):
            e.create(bind, checkfirst=True)

    op.create_table(
        "sub_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", _STATUS, nullable=False),
        sa.Column("data_entry_mode", _MODE, nullable=False),
        sa.Column("crm_style", _CRM, nullable=False),
        sa.Column("template", _TEMPLATE, nullable=False),
        sa.Column("brand_logo_url", sa.String(length=500), nullable=True),
        sa.Column("brand_primary_color", sa.String(length=7), nullable=True),
        sa.Column("brand_secondary_color", sa.String(length=7), nullable=True),
        sa.Column("brand_accent_color", sa.String(length=7), nullable=True),
        sa.Column("brand_font_heading", sa.String(length=100), nullable=True),
        sa.Column("brand_font_body", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("operator_user_id", "name", name="uq_sub_account_operator_name"),
        sa.UniqueConstraint("slug", name="uq_sub_accounts_slug"),
    )
    op.create_index("ix_sub_accounts_operator_user_id", "sub_accounts", ["operator_user_id"])
    op.create_index("ix_sub_accounts_slug", "sub_accounts", ["slug"])
    op.create_index("ix_sub_accounts_operator_status", "sub_accounts", ["operator_user_id", "status"])

    op.create_table(
        "sub_account_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sub_account_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sub_account_id"], ["sub_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("sub_account_id", "feature_key", name="uq_sub_account_feature"),
    )
    op.create_index("ix_sub_account_features_sub_account_id", "sub_account_features", ["sub_account_id"])

    op.add_column("users", sa.Column("sub_account_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("operator_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_users_sub_account_id", "users", ["sub_account_id"])
    op.create_index("ix_users_operator_id", "users", ["operator_id"])
    # FKs added on SQLite can't be ALTERed in; they are declared on the model and
    # enforced at create_all. On Postgres, add them explicitly.
    if bind.dialect.name == "postgresql":
        op.create_foreign_key("fk_users_sub_account_id", "users", "sub_accounts", ["sub_account_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_users_operator_id", "users", "users", ["operator_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("fk_users_operator_id", "users", type_="foreignkey")
        op.drop_constraint("fk_users_sub_account_id", "users", type_="foreignkey")
    op.drop_index("ix_users_operator_id", table_name="users")
    op.drop_index("ix_users_sub_account_id", table_name="users")
    op.drop_column("users", "is_platform_admin")
    op.drop_column("users", "operator_id")
    op.drop_column("users", "sub_account_id")

    op.drop_index("ix_sub_account_features_sub_account_id", table_name="sub_account_features")
    op.drop_table("sub_account_features")
    for ix in ("ix_sub_accounts_operator_status", "ix_sub_accounts_slug", "ix_sub_accounts_operator_user_id"):
        op.drop_index(ix, table_name="sub_accounts")
    op.drop_table("sub_accounts")

    if bind.dialect.name == "postgresql":
        for e in (_TEMPLATE, _CRM, _MODE, _STATUS):
            e.drop(bind, checkfirst=True)
