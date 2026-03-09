"""News briefing system

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add news preferences column to users table
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("news_preferences_json", sa.Text(), nullable=True))

    # Create news_cache table
    op.create_table(
        "news_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False, server_default="industry"),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_news_cache_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_cache_user_fetched", "news_cache", ["user_id", "fetched_at"])
    op.create_index("ix_news_cache_user_url", "news_cache", ["user_id", "url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_news_cache_user_url", table_name="news_cache")
    op.drop_index("ix_news_cache_user_fetched", table_name="news_cache")
    op.drop_table("news_cache")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("news_preferences_json")
