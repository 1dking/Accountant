"""add page_templates table

Revision ID: c9e1f2a3b4d5
Revises: b8d4e5f6a7c9
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa

revision = "c9e1f2a3b4d5"
down_revision = "b8d4e5f6a7c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_industry", sa.String(100), nullable=True),
        sa.Column("category_type", sa.String(100), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("css_content", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "scope",
            sa.Enum("ORG", "PLATFORM", name="templatescope"),
            nullable=False,
            server_default="ORG",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_templates_scope", "page_templates", ["scope"])
    op.create_index(
        "ix_page_templates_category",
        "page_templates",
        ["category_industry", "category_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_page_templates_category", table_name="page_templates")
    op.drop_index("ix_page_templates_scope", table_name="page_templates")
    op.drop_table("page_templates")
    op.execute("DROP TYPE IF EXISTS templatescope")
