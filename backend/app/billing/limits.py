"""Plan limit enforcement — makes the caps the pricing page advertises real.

Limits come from the platform-admin settings (max_pages_*, max_storage_*_gb,
obrain_*_messages) so the owner controls them in one place, and the plan comes
from the user's AccountSubscription. A limit of None means unlimited.

Enforcement is deliberately at the moment of consumption (publishing a page,
uploading a file, sending an O-Brain message) rather than a background sweep,
so a customer is never silently over their cap.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

BYTES_PER_GB = 1024 ** 3

# Which plans get unlimited of what. Mirrors the plan cards in BillingSettings.
_UNLIMITED_PAGES = {"enterprise"}
_UNLIMITED_STORAGE = {"enterprise"}
_UNLIMITED_AI = {"business", "enterprise"}


class PlanLimitError(AppError):
    """402 Payment Required — the account is at its plan's cap."""

    def __init__(self, message: str, resource: str, used: int, limit: int):
        super().__init__(code="PLAN_LIMIT_REACHED", message=message, status_code=402)
        self.resource = resource
        self.used = used
        self.limit = limit


async def _settings_map(db: AsyncSession) -> dict[str, str]:
    from app.platform_admin.service import list_platform_settings

    rows = []
    for category in ("limits", "pricing"):
        rows.extend(await list_platform_settings(db, category))
    return {r.key: r.value for r in rows}


def _as_int(raw: str | None, default: int) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


async def get_plan_key(db: AsyncSession, user: User) -> str:
    from app.billing.service import get_subscription

    sub = await get_subscription(db, user)
    return sub.plan_key or "starter"


async def get_limits(db: AsyncSession, plan_key: str) -> dict[str, int | None]:
    """Resolve this plan's caps. None = unlimited."""
    s = await _settings_map(db)

    pages = None if plan_key in _UNLIMITED_PAGES else _as_int(
        s.get(f"max_pages_{plan_key}"), {"starter": 3, "pro": 25, "business": 100}.get(plan_key, 3)
    )
    storage_gb = None if plan_key in _UNLIMITED_STORAGE else _as_int(
        s.get(f"max_storage_{plan_key}_gb"), {"starter": 1, "pro": 10, "business": 50}.get(plan_key, 1)
    )
    if plan_key in _UNLIMITED_AI:
        ai = None
    elif plan_key == "pro":
        ai = _as_int(s.get("obrain_pro_messages"), 500)
    else:
        ai = _as_int(s.get("obrain_free_messages"), 50)

    return {
        "pages": pages,
        "storage_bytes": None if storage_gb is None else storage_gb * BYTES_PER_GB,
        "ai_messages": ai,
    }


# ── Usage counters ───────────────────────────────────────────────────────


async def count_published_pages(db: AsyncSession, user: User) -> int:
    from app.pages.models import Page, PageStatus

    return await db.scalar(
        select(func.count())
        .select_from(Page)
        .where(Page.created_by == user.id, Page.status == PageStatus.PUBLISHED)
    ) or 0


async def sum_storage_bytes(db: AsyncSession, user: User) -> int:
    from app.documents.models import Document

    return await db.scalar(
        select(func.coalesce(func.sum(Document.file_size), 0)).where(
            Document.uploaded_by == user.id
        )
    ) or 0


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def count_ai_messages_this_month(db: AsyncSession, user: User) -> int:
    """Only the user's own messages count — assistant replies are not billed."""
    from app.brain.models import BrainConversation, BrainMessage

    return await db.scalar(
        select(func.count())
        .select_from(BrainMessage)
        .join(BrainConversation, BrainMessage.conversation_id == BrainConversation.id)
        .where(
            BrainConversation.user_id == user.id,
            BrainMessage.role == "user",
            BrainMessage.created_at >= _month_start(),
        )
    ) or 0


# ── Enforcement ──────────────────────────────────────────────────────────


def _fmt_gb(b: int) -> str:
    return f"{b / BYTES_PER_GB:.1f} GB"


async def enforce_page_limit(db: AsyncSession, user: User) -> None:
    plan = await get_plan_key(db, user)
    limit = (await get_limits(db, plan))["pages"]
    if limit is None:
        return
    used = await count_published_pages(db, user)
    if used >= limit:
        raise PlanLimitError(
            f"Your {plan.title()} plan includes {limit} published pages and you have {used}. "
            "Upgrade your plan to publish more.",
            resource="pages", used=used, limit=limit,
        )


async def enforce_storage_limit(db: AsyncSession, user: User, incoming_bytes: int = 0) -> None:
    plan = await get_plan_key(db, user)
    limit = (await get_limits(db, plan))["storage_bytes"]
    if limit is None:
        return
    used = await sum_storage_bytes(db, user)
    if used + incoming_bytes > limit:
        raise PlanLimitError(
            f"Your {plan.title()} plan includes {_fmt_gb(limit)} of storage and you have used "
            f"{_fmt_gb(used)}. Upgrade your plan or remove some files.",
            resource="storage", used=used, limit=limit,
        )


async def enforce_ai_message_limit(db: AsyncSession, user: User) -> None:
    plan = await get_plan_key(db, user)
    limit = (await get_limits(db, plan))["ai_messages"]
    if limit is None:
        return
    used = await count_ai_messages_this_month(db, user)
    if used >= limit:
        raise PlanLimitError(
            f"Your {plan.title()} plan includes {limit} O-Brain messages per month and you have "
            f"used {used}. Upgrade your plan for more.",
            resource="ai_messages", used=used, limit=limit,
        )


async def get_usage_summary(db: AsyncSession, user: User) -> dict:
    """Everything the billing page needs to show usage-vs-plan."""
    plan = await get_plan_key(db, user)
    limits = await get_limits(db, plan)
    return {
        "plan_key": plan,
        "pages": {"used": await count_published_pages(db, user), "limit": limits["pages"]},
        "storage": {
            "used": await sum_storage_bytes(db, user),
            "limit": limits["storage_bytes"],
        },
        "ai_messages": {
            "used": await count_ai_messages_this_month(db, user),
            "limit": limits["ai_messages"],
        },
    }
