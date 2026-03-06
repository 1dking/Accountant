"""Tests for the unified inbox API (/api/inbox).

Covers: service-level record helpers, dedup, message listing with filters,
thread grouping, read status, unread counts, and auth guards.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.inbox.models import MessageDirection, MessageType, UnifiedMessage
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def seed_messages(db: AsyncSession, admin_user: User):
    """Seed 3 outbound email messages in the same thread."""
    msgs = []
    for i in range(3):
        msg = UnifiedMessage(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            message_type=MessageType.EMAIL,
            direction=MessageDirection.OUTBOUND,
            subject=f"Test Subject {i}",
            body=f"Test body {i}",
            recipient="test@example.com",
            is_read=False,
            thread_id="email:test@example.com",
            source_type="test",
            source_id=f"test-{i}",
        )
        msgs.append(msg)
    db.add_all(msgs)
    await db.commit()
    for m in msgs:
        await db.refresh(m)
    return msgs


# =========================================================================
# 1. Service-level: record outbound email
# =========================================================================


@pytest.mark.asyncio
async def test_record_outbound_email_creates_message(
    db: AsyncSession, admin_user: User
):
    from app.inbox.service import record_outbound_email

    msg = await record_outbound_email(
        db,
        user_id=admin_user.id,
        to_email="alice@example.com",
        subject="Hello",
        body_snippet="Hi Alice",
        source_type="test",
        source_id="email-1",
    )
    await db.commit()

    assert msg.message_type == MessageType.EMAIL
    assert msg.direction == MessageDirection.OUTBOUND
    assert msg.recipient == "alice@example.com"
    assert msg.subject == "Hello"
    assert msg.body == "Hi Alice"
    assert msg.is_read is True  # outbound = already read
    assert msg.thread_id == "email:alice@example.com"


# =========================================================================
# 2. Service-level: record outbound SMS
# =========================================================================


@pytest.mark.asyncio
async def test_record_outbound_sms_creates_message(
    db: AsyncSession, admin_user: User
):
    from app.inbox.service import record_outbound_sms

    msg = await record_outbound_sms(
        db,
        user_id=admin_user.id,
        to_phone="+15551234567",
        body="Hey there",
        source_type="test",
        source_id="sms-1",
    )
    await db.commit()

    assert msg.message_type == MessageType.SMS
    assert msg.direction == MessageDirection.OUTBOUND
    assert msg.recipient == "+15551234567"
    assert msg.body == "Hey there"
    assert msg.subject is None
    assert msg.thread_id == "sms:+15551234567"


# =========================================================================
# 3. Dedup: same source_type + source_id recorded twice
# =========================================================================


@pytest.mark.asyncio
async def test_dedup_prevents_duplicate(db: AsyncSession, admin_user: User):
    from app.inbox.service import record_outbound_email

    msg1 = await record_outbound_email(
        db,
        user_id=admin_user.id,
        to_email="dup@example.com",
        subject="Dup",
        body_snippet="First",
        source_type="invoice",
        source_id="inv-42",
    )
    await db.commit()

    msg2 = await record_outbound_email(
        db,
        user_id=admin_user.id,
        to_email="dup@example.com",
        subject="Dup Again",
        body_snippet="Second",
        source_type="invoice",
        source_id="inv-42",
    )
    await db.commit()

    # Should return the same message, not create a new one
    assert msg1.id == msg2.id

    result = await db.execute(
        select(UnifiedMessage).where(
            UnifiedMessage.source_type == "invoice",
            UnifiedMessage.source_id == "inv-42",
        )
    )
    assert len(result.scalars().all()) == 1


# =========================================================================
# 4. List messages returns user's messages
# =========================================================================


@pytest.mark.asyncio
async def test_list_messages_returns_user_messages(
    client: AsyncClient, admin_user: User, seed_messages
):
    resp = await client.get(
        "/api/inbox/messages",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total_count"] == 3
    assert len(data["data"]) == 3


# =========================================================================
# 5. List messages filters by type
# =========================================================================


@pytest.mark.asyncio
async def test_list_messages_filters_by_type(
    client: AsyncClient, db: AsyncSession, admin_user: User, seed_messages
):
    # Add an SMS message alongside the seeded emails
    sms = UnifiedMessage(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        message_type=MessageType.SMS,
        direction=MessageDirection.OUTBOUND,
        body="SMS body",
        recipient="+15559999999",
        is_read=False,
        thread_id="sms:+15559999999",
        source_type="test",
        source_id="sms-filter-1",
    )
    db.add(sms)
    await db.commit()

    # Filter by email only
    resp = await client.get(
        "/api/inbox/messages?message_type=email",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total_count"] == 3
    for msg in data["data"]:
        assert msg["message_type"] == "email"


# =========================================================================
# 6. List threads groups by thread_id
# =========================================================================


@pytest.mark.asyncio
async def test_list_threads_groups_by_thread_id(
    client: AsyncClient, admin_user: User, seed_messages
):
    resp = await client.get(
        "/api/inbox/threads",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    # All 3 seed messages share one thread_id
    assert data["meta"]["total_count"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["message_count"] == 3


# =========================================================================
# 7. Mark message as read
# =========================================================================


@pytest.mark.asyncio
async def test_mark_message_as_read(
    client: AsyncClient, db: AsyncSession, admin_user: User, seed_messages
):
    msg = seed_messages[0]
    assert msg.is_read is False

    resp = await client.post(
        f"/api/inbox/messages/{msg.id}/read",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    await db.refresh(msg)
    assert msg.is_read is True


# =========================================================================
# 8. Mark thread as read
# =========================================================================


@pytest.mark.asyncio
async def test_mark_thread_as_read(
    client: AsyncClient, db: AsyncSession, admin_user: User, seed_messages
):
    thread_id = seed_messages[0].thread_id

    resp = await client.post(
        f"/api/inbox/threads/{thread_id}/read",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    # All messages in the thread should now be read
    for msg in seed_messages:
        await db.refresh(msg)
        assert msg.is_read is True


# =========================================================================
# 9. Unread count
# =========================================================================


@pytest.mark.asyncio
async def test_unread_count(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    # Create 2 unread emails and 1 unread SMS
    for i in range(2):
        db.add(
            UnifiedMessage(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                message_type=MessageType.EMAIL,
                direction=MessageDirection.INBOUND,
                subject=f"Unread email {i}",
                is_read=False,
                thread_id=f"email:unread-{i}@example.com",
                source_type="test",
                source_id=f"unread-email-{i}",
            )
        )
    db.add(
        UnifiedMessage(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            message_type=MessageType.SMS,
            direction=MessageDirection.INBOUND,
            body="Unread sms",
            is_read=False,
            thread_id="sms:+15550000000",
            source_type="test",
            source_id="unread-sms-0",
        )
    )
    await db.commit()

    resp = await client.get(
        "/api/inbox/unread-count",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    counts = resp.json()["data"]
    assert counts["total"] == 3
    assert counts["email"] == 2
    assert counts["sms"] == 1


# =========================================================================
# 10. Get thread messages (chronological order)
# =========================================================================


@pytest.mark.asyncio
async def test_get_thread_messages(
    client: AsyncClient, admin_user: User, seed_messages
):
    thread_id = seed_messages[0].thread_id

    resp = await client.get(
        f"/api/inbox/threads/{thread_id}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3

    # Verify chronological order (ascending created_at)
    timestamps = [m["created_at"] for m in data]
    assert timestamps == sorted(timestamps)


# =========================================================================
# 11. Unauthenticated returns 401
# =========================================================================


@pytest.mark.asyncio
async def test_unauthenticated_401(client: AsyncClient):
    resp = await client.get("/api/inbox/messages")
    assert resp.status_code == 401
