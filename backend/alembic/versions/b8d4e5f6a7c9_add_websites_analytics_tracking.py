"""Add websites, page_visits, page_events, page_analytics_daily, tracking fields

Revision ID: b8d4e5f6a7c9
Revises: a7c3f2d91e4b
Create Date: 2026-03-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4e5f6a7c9'
down_revision: Union[str, None] = 'a7c3f2d91e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── websites table ──────────────────────────────────────────────
    op.create_table(
        'websites',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('favicon_url', sa.String(500), nullable=True),
        sa.Column('global_css', sa.Text(), nullable=True),
        sa.Column('nav_config_json', sa.Text(), nullable=True),
        sa.Column('header_html', sa.Text(), nullable=True),
        sa.Column('footer_html', sa.Text(), nullable=True),
        sa.Column('seo_defaults_json', sa.Text(), nullable=True),
        sa.Column('tracking_pixels_json', sa.Text(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_websites_slug', 'websites', ['slug'])

    # ── Add columns to pages ────────────────────────────────────────
    with op.batch_alter_table('pages') as batch_op:
        batch_op.add_column(sa.Column('website_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('page_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('tracking_pixels_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('chat_history_json', sa.Text(), nullable=True))
        batch_op.create_index('ix_pages_website_id', ['website_id'])
        batch_op.create_foreign_key(
            'fk_pages_website', 'websites', ['website_id'], ['id'], ondelete='CASCADE',
        )

    # ── page_visits table ───────────────────────────────────────────
    op.create_table(
        'page_visits',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('website_id', sa.Uuid(), sa.ForeignKey('websites.id', ondelete='SET NULL'), nullable=True),
        sa.Column('visitor_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('referrer', sa.String(500), nullable=True),
        sa.Column('utm_source', sa.String(255), nullable=True),
        sa.Column('utm_medium', sa.String(255), nullable=True),
        sa.Column('utm_campaign', sa.String(255), nullable=True),
        sa.Column('device_type', sa.String(20), nullable=True),
        sa.Column('browser', sa.String(100), nullable=True),
        sa.Column('os', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('ip_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_page_visits_page_id', 'page_visits', ['page_id'])
    op.create_index('ix_page_visits_visitor_id', 'page_visits', ['visitor_id'])

    # ── page_events table ───────────────────────────────────────────
    op.create_table(
        'page_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('visit_id', sa.Uuid(), sa.ForeignKey('page_visits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_page_events_visit_id', 'page_events', ['visit_id'])
    op.create_index('ix_page_events_page_id', 'page_events', ['page_id'])

    # ── page_analytics_daily table ──────────────────────────────────
    op.create_table(
        'page_analytics_daily',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('visitors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unique_visitors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('page_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bounce_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scroll_25_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scroll_50_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scroll_75_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scroll_100_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('click_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('form_submit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_page_analytics_daily_page_id', 'page_analytics_daily', ['page_id'])
    op.create_index('ix_page_analytics_daily_date', 'page_analytics_daily', ['page_id', 'date'])


def downgrade() -> None:
    op.drop_table('page_analytics_daily')
    op.drop_table('page_events')
    op.drop_table('page_visits')
    with op.batch_alter_table('pages') as batch_op:
        batch_op.drop_constraint('fk_pages_website', type_='foreignkey')
        batch_op.drop_index('ix_pages_website_id')
        batch_op.drop_column('chat_history_json')
        batch_op.drop_column('tracking_pixels_json')
        batch_op.drop_column('page_order')
        batch_op.drop_column('website_id')
    op.drop_table('websites')
