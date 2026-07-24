"""Tests for plan limit enforcement.

The pricing page advertises caps (pages, storage, O-Brain messages); these
tests prove they're actually enforced, that upgrading lifts them, and that
higher tiers are genuinely unlimited.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing import limits, service
from app.core.exceptions import AppError
from app.pages.models import Page, PageStatus
from app.platform_admin.models import PlatformSetting


async def _seed_limits(db: AsyncSession) -> None:
    db.add_all([
        PlatformSetting(key="max_pages_starter", value="3", category="limits"),
        PlatformSetting(key="max_pages_pro", value="25", category="limits"),
        PlatformSetting(key="max_storage_starter_gb", value="1", category="limits"),
        PlatformSetting(key="obrain_free_messages", value="50", category="pricing"),
        PlatformSetting(key="obrain_pro_messages", value="500", category="pricing"),
    ])
    await db.commit()


async def _set_plan(db: AsyncSession, user: User, plan_key: str) -> None:
    sub = await service.get_subscription(db, user)
    sub.plan_key = plan_key
    await db.commit()


async def _add_published_pages(db: AsyncSession, user: User, n: int) -> None:
    for i in range(n):
        db.add(Page(
            id=uuid.uuid4(),
            title=f"Page {i}",
            slug=f"page-{uuid.uuid4().hex[:8]}",
            status=PageStatus.PUBLISHED,
            created_by=user.id,
        ))
    await db.commit()


# ── Limit resolution ─────────────────────────────────────────────────────


@pytest.mark.normal
async def test_limits_resolve_per_plan(db: AsyncSession):
    await _seed_limits(db)
    starter = await limits.get_limits(db, "starter")
    pro = await limits.get_limits(db, "pro")
    business = await limits.get_limits(db, "business")
    enterprise = await limits.get_limits(db, "enterprise")

    assert starter["pages"] == 3
    assert starter["ai_messages"] == 50
    assert starter["storage_bytes"] == 1 * limits.BYTES_PER_GB

    assert pro["pages"] == 25
    assert pro["ai_messages"] == 500

    # Business gets unlimited AI; enterprise is unlimited across the board.
    assert business["ai_messages"] is None
    assert enterprise["pages"] is None
    assert enterprise["storage_bytes"] is None
    assert enterprise["ai_messages"] is None


# ── Pages ────────────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_page_limit_blocks_at_cap(db: AsyncSession, admin_user: User):
    """Starter allows 3 published pages — the 4th publish is refused."""
    await _seed_limits(db)
    await _add_published_pages(db, admin_user, 3)

    with pytest.raises(AppError) as exc:
        await limits.enforce_page_limit(db, admin_user)
    assert exc.value.status_code == 402
    assert exc.value.code == "PLAN_LIMIT_REACHED"


@pytest.mark.critical
async def test_page_limit_allows_under_cap(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    await _add_published_pages(db, admin_user, 2)
    await limits.enforce_page_limit(db, admin_user)  # must not raise


@pytest.mark.critical
async def test_upgrading_plan_lifts_page_limit(db: AsyncSession, admin_user: User):
    """The whole point of billing: paying raises the cap."""
    await _seed_limits(db)
    await _add_published_pages(db, admin_user, 3)

    with pytest.raises(AppError):
        await limits.enforce_page_limit(db, admin_user)

    await _set_plan(db, admin_user, "pro")
    await limits.enforce_page_limit(db, admin_user)  # 3 < 25, now fine


@pytest.mark.normal
async def test_enterprise_pages_unlimited(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    await _add_published_pages(db, admin_user, 40)
    await _set_plan(db, admin_user, "enterprise")
    await limits.enforce_page_limit(db, admin_user)  # must not raise


@pytest.mark.normal
async def test_draft_pages_do_not_count(db: AsyncSession, admin_user: User):
    """Only PUBLISHED pages consume the cap — drafts are free."""
    await _seed_limits(db)
    for i in range(10):
        db.add(Page(
            id=uuid.uuid4(),
            title=f"Draft {i}",
            slug=f"draft-{uuid.uuid4().hex[:8]}",
            status=PageStatus.DRAFT,
            created_by=admin_user.id,
        ))
    await db.commit()
    assert await limits.count_published_pages(db, admin_user) == 0
    await limits.enforce_page_limit(db, admin_user)


@pytest.mark.normal
async def test_another_users_pages_do_not_count(
    db: AsyncSession, admin_user: User, team_member_user: User
):
    """Limits are per account — someone else's pages must not consume mine."""
    await _seed_limits(db)
    await _add_published_pages(db, team_member_user, 5)
    assert await limits.count_published_pages(db, admin_user) == 0
    await limits.enforce_page_limit(db, admin_user)


# ── Storage ──────────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_storage_limit_rejects_oversized_upload(
    db: AsyncSession, admin_user: User
):
    """An upload that would push the account past its cap is refused before
    anything is stored."""
    await _seed_limits(db)
    over = 2 * limits.BYTES_PER_GB  # Starter cap is 1 GB

    with pytest.raises(AppError) as exc:
        await limits.enforce_storage_limit(db, admin_user, incoming_bytes=over)
    assert exc.value.status_code == 402


@pytest.mark.normal
async def test_storage_limit_allows_small_upload(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    await limits.enforce_storage_limit(db, admin_user, incoming_bytes=1024)


# ── AI messages ──────────────────────────────────────────────────────────


@pytest.mark.normal
async def test_ai_messages_start_at_zero(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    assert await limits.count_ai_messages_this_month(db, admin_user) == 0
    await limits.enforce_ai_message_limit(db, admin_user)


@pytest.mark.normal
async def test_business_plan_ai_unlimited(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    await _set_plan(db, admin_user, "business")
    # Even with the counter irrelevant, business must never be blocked.
    await limits.enforce_ai_message_limit(db, admin_user)


# ── Usage summary ────────────────────────────────────────────────────────


@pytest.mark.normal
async def test_usage_summary_shape(db: AsyncSession, admin_user: User):
    await _seed_limits(db)
    await _add_published_pages(db, admin_user, 2)
    summary = await limits.get_usage_summary(db, admin_user)

    assert summary["plan_key"] == "starter"
    assert summary["pages"] == {"used": 2, "limit": 3}
    assert summary["storage"]["limit"] == 1 * limits.BYTES_PER_GB
    assert summary["ai_messages"]["limit"] == 50
