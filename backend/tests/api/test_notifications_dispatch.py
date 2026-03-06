"""Tests for the notification dispatch helpers (notify_user, notify_admins)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.notifications.dispatch import notify_admins, notify_user
from app.notifications.models import Notification
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. notify_user
# ---------------------------------------------------------------------------


async def test_notify_user_creates_notification(
    db: AsyncSession, admin_user: User
):
    """notify_user creates a notification record in DB."""
    notification = await notify_user(
        db,
        user_id=admin_user.id,
        type="info",
        title="Test Notification",
        message="This is a test notification",
    )

    assert notification is not None
    assert notification.id is not None

    # Verify it is persisted in the DB
    result = await db.execute(
        select(Notification).where(Notification.id == notification.id)
    )
    persisted = result.scalar_one_or_none()
    assert persisted is not None
    assert persisted.user_id == admin_user.id


async def test_notify_user_correct_fields(
    db: AsyncSession, admin_user: User
):
    """notify_user creates notification with correct fields."""
    notification = await notify_user(
        db,
        user_id=admin_user.id,
        type="invoice",
        title="Invoice Paid",
        message="Invoice INV-001 was paid",
        resource_type="invoice",
        resource_id="some-uuid-here",
    )

    assert notification.type == "invoice"
    assert notification.title == "Invoice Paid"
    assert notification.message == "Invoice INV-001 was paid"
    assert notification.resource_type == "invoice"
    assert notification.resource_id == "some-uuid-here"
    assert notification.is_read is False
    assert notification.user_id == admin_user.id


# ---------------------------------------------------------------------------
# 2. notify_admins
# ---------------------------------------------------------------------------


async def test_notify_admins_notifies_all_admin_users(
    db: AsyncSession, admin_user: User, team_member_user: User
):
    """notify_admins creates notifications for all admin users (not team members)."""
    notifications = await notify_admins(
        db,
        type="system",
        title="System Alert",
        message="Something happened",
    )

    # Should have at least 1 notification (for admin_user)
    assert len(notifications) >= 1

    # All notifications should be for admin users
    admin_ids = {str(admin_user.id)}
    notified_user_ids = {str(n.user_id) for n in notifications}
    # Every notified user should be an admin
    assert admin_ids.issubset(notified_user_ids)
    # team_member_user should NOT have been notified
    assert str(team_member_user.id) not in notified_user_ids


# ---------------------------------------------------------------------------
# 3. Readable via API
# ---------------------------------------------------------------------------


async def test_notification_readable_via_api(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """Notification created by notify_user is readable via GET /api/notifications."""
    # Create a notification via the dispatch helper
    notification = await notify_user(
        db,
        user_id=admin_user.id,
        type="test",
        title="API Readable",
        message="Check this via API",
    )

    # Read it back through the API
    resp = await client.get(
        "/api/notifications", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body

    # Find our notification in the list
    notif_ids = [n["id"] for n in body["data"]]
    assert str(notification.id) in notif_ids

    # Verify the fields match
    found = next(n for n in body["data"] if n["id"] == str(notification.id))
    assert found["type"] == "test"
    assert found["title"] == "API Readable"
    assert found["message"] == "Check this via API"
    assert found["is_read"] is False
