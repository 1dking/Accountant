import pathlib

target = pathlib.Path(r"C:/Users/Owner/Desktop/Dev/Accountant/backend/alembic/versions/e1e481069afe_page_builder_v2_domains_split_tests_logo.py")
text = target.read_text()

# We need to rewrite upgrade() and downgrade() to only contain our intended changes.
# Strategy: keep everything up to "def upgrade()" then write our own upgrade/downgrade.

header_end = text.index("def upgrade()")
header = text[:header_end]

new_code = """def upgrade() -> None:
    # --- New tables ---
    op.create_table("custom_domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("website_id", sa.Uuid(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("domain_type", sa.String(length=20), nullable=False),
        sa.Column("dns_record_type", sa.String(length=10), nullable=False),
        sa.Column("dns_target", sa.String(length=255), nullable=True),
        sa.Column("dns_verified", sa.Boolean(), nullable=False),
        sa.Column("ssl_status", sa.String(length=20), nullable=False),
        sa.Column("ssl_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain")
    )
"""

print("This approach is getting too complex with escaping. Using a different method.")
