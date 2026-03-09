"""Brain pending actions table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brain_pending_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("brain_conversations.id", ondelete="CASCADE", name="fk_bpa_conv"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_bpa_user"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_bpa_user_status", "brain_pending_actions", ["user_id", "status"])
    op.create_index("ix_bpa_conv", "brain_pending_actions", ["conversation_id"])

    # Annual pricing settings
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'plan_starter_annual_price', '81', 'pricing', 'Starter plan annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'plan_starter_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'plan_pro_annual_price', '164', 'pricing', 'Pro plan annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'plan_pro_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'plan_business_annual_price', '331', 'pricing', 'Business plan annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'plan_business_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'plan_enterprise_annual_price', '499', 'pricing', 'Enterprise plan annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'plan_enterprise_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_essential_price', '49', 'pricing', 'O-Brain Essential monthly price ($)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_essential_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_pro_price', '99', 'pricing', 'O-Brain Pro monthly price ($)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_pro_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_coach_price', '199', 'pricing', 'O-Brain Coach monthly price ($)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_coach_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_essential_annual_price', '41', 'pricing', 'O-Brain Essential annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_essential_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_pro_annual_price', '83', 'pricing', 'O-Brain Pro annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_pro_annual_price')
    """)
    op.execute("""
        INSERT INTO platform_settings (id, key, value, category, description, value_type, created_at, updated_at)
        SELECT gen_random_uuid(), 'obrain_coach_annual_price', '166', 'pricing', 'O-Brain Coach annual price ($/mo billed yearly)', 'number', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = 'obrain_coach_annual_price')
    """)


def downgrade() -> None:
    op.drop_index("ix_bpa_conv", table_name="brain_pending_actions")
    op.drop_index("ix_bpa_user_status", table_name="brain_pending_actions")
    op.drop_table("brain_pending_actions")

    for key in [
        "plan_starter_annual_price", "plan_pro_annual_price",
        "plan_business_annual_price", "plan_enterprise_annual_price",
        "obrain_essential_price", "obrain_pro_price", "obrain_coach_price",
        "obrain_essential_annual_price", "obrain_pro_annual_price", "obrain_coach_annual_price",
    ]:
        op.execute(f"DELETE FROM platform_settings WHERE key = '{key}'")
