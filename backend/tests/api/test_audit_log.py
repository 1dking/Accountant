"""Security audit trail — login events recorded, admin-queryable, access-gated."""

import pytest
from sqlalchemy import select

from app.audit.models import AuditLog
from app.audit.service import AuditAction
from tests.conftest import auth_header

PASSWORD = "TestPass123!"


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    # The login limiter is process-global in-memory; clear it so bursts across
    # tests don't spuriously 429.
    from app.auth import router as auth_router

    auth_router._login_attempts.clear()
    yield


@pytest.mark.asyncio
async def test_login_success_and_failure_are_audited(client, admin_user, db):
    await client.post("/api/auth/login", json={"email": admin_user.email, "password": "wrong"})
    await client.post("/api/auth/login", json={"email": admin_user.email, "password": PASSWORD})

    actions = (await db.execute(select(AuditLog.action))).scalars().all()
    assert AuditAction.LOGIN_FAILURE in actions
    assert AuditAction.LOGIN_SUCCESS in actions


@pytest.mark.asyncio
async def test_admin_can_query_and_filter_audit(client, admin_user):
    await client.post("/api/auth/login", json={"email": admin_user.email, "password": PASSWORD})

    r = await client.get(
        "/api/platform-admin/audit?action=login_success", headers=auth_header(admin_user)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data) >= 1
    assert all(row["action"] == "login_success" for row in data)
    assert "total" in r.json()["meta"]


@pytest.mark.asyncio
async def test_non_admin_cannot_query_audit(client, viewer_user):
    r = await client.get("/api/platform-admin/audit", headers=auth_header(viewer_user))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_rows_are_append_only_shape(client, admin_user, db):
    """A recorded row carries actor + result + timestamp (the demonstrable trail)."""
    await client.post("/api/auth/login", json={"email": admin_user.email, "password": PASSWORD})
    row = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_SUCCESS)
        )
    ).scalars().first()
    assert row is not None
    assert row.actor_email == admin_user.email
    assert row.result == "success"
    assert row.created_at is not None
