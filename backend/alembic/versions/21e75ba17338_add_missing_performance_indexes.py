"""add missing performance indexes

Revision ID: 21e75ba17338
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 00:25:52.738697

Adds indexes to status fields, date fields, and composite indexes
for high-traffic query patterns identified in health audit.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '21e75ba17338'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(connection, table_name: str, index_name: str) -> bool:
    """Check whether an index already exists (works for both SQLite and PG)."""
    insp = inspect(connection)
    for idx in insp.get_indexes(table_name):
        if idx["name"] == index_name:
            return True
    return False


def _create_index_safe(index_name: str, table_name: str, columns: list[str]) -> None:
    """Create an index only if it doesn't already exist."""
    conn = op.get_bind()
    if not _index_exists(conn, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    # --- Tier 1: Critical (business-critical query paths) ---

    # Invoice status/date filtering (list, stats, overdue checks, reports)
    _create_index_safe("ix_invoices_status", "invoices", ["status"])
    _create_index_safe("ix_invoices_due_date", "invoices", ["due_date"])
    _create_index_safe("ix_invoices_issue_date", "invoices", ["issue_date"])

    # Expense status filtering (list, approval workflows, reports)
    _create_index_safe("ix_expenses_status", "expenses", ["status"])

    # Expense approval status (pending approval lookups)
    _create_index_safe("ix_expense_approvals_status", "expense_approvals", ["status"])

    # --- Tier 2: High (frequently queried status fields) ---

    # Approval workflow status (collaboration pending approvals)
    _create_index_safe("ix_approval_workflows_status", "approval_workflows", ["status"])

    # Document status filtering
    _create_index_safe("ix_documents_status", "documents", ["status"])

    # Estimate status filtering
    _create_index_safe("ix_estimates_status", "estimates", ["status"])

    # Credit note status filtering
    _create_index_safe("ix_credit_notes_status", "credit_notes", ["status"])

    # --- Tier 3: Medium (supporting queries) ---

    # Meeting recording status
    _create_index_safe("ix_meeting_recordings_status", "meeting_recordings", ["status"])

    # Activity log filtering by resource type
    _create_index_safe("ix_activity_logs_resource_type", "activity_logs", ["resource_type"])

    # --- Composite indexes for common query patterns ---

    # Invoice: find unpaid invoices for a contact
    _create_index_safe("ix_invoices_contact_status", "invoices", ["contact_id", "status"])

    # Expense: list expenses by date (for reports)
    _create_index_safe("ix_expenses_date", "expenses", ["date"])


def downgrade() -> None:
    conn = op.get_bind()

    # Only drop indexes that exist (safe for partial upgrades)
    for index_name, table_name in [
        ("ix_expenses_date", "expenses"),
        ("ix_invoices_contact_status", "invoices"),
        ("ix_activity_logs_resource_type", "activity_logs"),
        ("ix_meeting_recordings_status", "meeting_recordings"),
        ("ix_credit_notes_status", "credit_notes"),
        ("ix_estimates_status", "estimates"),
        ("ix_documents_status", "documents"),
        ("ix_approval_workflows_status", "approval_workflows"),
        ("ix_expense_approvals_status", "expense_approvals"),
        ("ix_expenses_status", "expenses"),
        ("ix_invoices_issue_date", "invoices"),
        ("ix_invoices_due_date", "invoices"),
        ("ix_invoices_status", "invoices"),
    ]:
        if _index_exists(conn, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
