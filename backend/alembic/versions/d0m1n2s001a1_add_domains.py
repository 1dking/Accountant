"""Add domain reseller tables (S8)

Revision ID: d0m1n2s001a1
Revises: m1j2k3l4m5n6
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0m1n2s001a1"
down_revision: Union[str, None] = "m1j2k3l4m5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_purchases",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("tld", sa.String(64), nullable=False),
        sa.Column("partner", sa.String(32), nullable=False, server_default="porkbun"),
        sa.Column("partner_reference", sa.String(255), nullable=True),
        sa.Column("price_cents_paid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("price_cents_wholesale", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("years", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("stripe_checkout_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("domain", name="uq_domain_purchases_domain"),
    )
    op.create_index("ix_domain_purchases_created_by", "domain_purchases", ["created_by"])
    op.create_index("ix_domain_purchases_org_id", "domain_purchases", ["org_id"])
    op.create_index("ix_domain_purchases_tld", "domain_purchases", ["tld"])
    op.create_index("ix_domain_purchases_status", "domain_purchases", ["status"])
    op.create_index("ix_domain_purchases_expires_at", "domain_purchases", ["expires_at"])
    op.create_index("ix_domain_purchases_stripe_checkout_id",
                    "domain_purchases", ["stripe_checkout_id"])

    op.create_table(
        "dns_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("domain_purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_record_id", sa.String(255), nullable=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("ttl", sa.Integer, nullable=False, server_default="600"),
        sa.Column("priority", sa.Integer, nullable=True),
        sa.Column("extra", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_dns_records_domain_id", "dns_records", ["domain_id"])
    op.create_index("ix_dns_records_partner_record_id", "dns_records", ["partner_record_id"])
    op.create_index("ix_dns_records_domain_type", "dns_records", ["domain_id", "type"])


def downgrade() -> None:
    op.drop_index("ix_dns_records_domain_type", table_name="dns_records")
    op.drop_index("ix_dns_records_partner_record_id", table_name="dns_records")
    op.drop_index("ix_dns_records_domain_id", table_name="dns_records")
    op.drop_table("dns_records")
    for i in (
        "ix_domain_purchases_stripe_checkout_id",
        "ix_domain_purchases_expires_at",
        "ix_domain_purchases_status",
        "ix_domain_purchases_tld",
        "ix_domain_purchases_org_id",
        "ix_domain_purchases_created_by",
    ):
        op.drop_index(i, table_name="domain_purchases")
    op.drop_table("domain_purchases")
