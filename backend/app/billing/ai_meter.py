"""The single AI spend meter.

Before this module the only AI guard was ``enforce_ai_message_limit``, called
from exactly one endpoint (``brain/router.py``). Eleven other model paths —
Drive auto-extraction, Smart Import, meeting summaries, quote drafts, Coach,
Gmail scan, Plaid categorisation, page generation, in-document assist,
transcription, embeddings — were completely ungated on every plan.

Every model invocation now goes through :func:`consume`.

**Credits:** 1 credit = $0.001 of estimated model spend. Integers, not floats,
so concurrent increments can't drift. The per-operation costs below come from
the estimates in COST_LEDGER.md and are deliberately conservative (round up):
under-charging here means real money leaks.

**Tenant key** mirrors ``events.service.resolve_org_id`` — the org id when the
user has one, else the user's own id — so an agency meters as one tenant.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import AiUsage
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

#: Estimated spend per invocation, in credits (1 credit = $0.001).
#: Keep in step with COST_LEDGER.md Part 3.
AI_OPERATION_COSTS: dict[str, int] = {
    "chat": 18,                  # ~$0.018 — Claude 2048 out + RAG context
    "doc_extract": 15,           # ~$0.015 — Claude vision per document
    "smart_import": 54,          # ~$0.054 — 4096-token batch
    "meeting_summary": 60,       # ~$0.060
    "quote_draft": 44,           # ~$0.044
    "coach_report": 90,          # ~$0.090
    "coach_nudge": 14,           # ~$0.0135
    "gmail_parse": 15,           # ~$0.015 per email
    "plaid_categorize": 50,      # ~$0.050 per sync
    "page_generate": 7,          # ~$0.007 Gemini (Claude fallback re-charges)
    "page_generate_fallback": 240,  # ~$0.240 — Claude 16k out
    "doc_assist": 12,            # ~$0.012 — in-document AI
    "contact_brief": 20,         # ~$0.020
    "transcription_minute": 6,   # ~$0.006 per audio minute
    "embedding_batch": 1,        # ~$0.001 — negligible but not free
    "news_digest": 10,           # ~$0.010
    "workflow_ask_obrain": 18,   # ~$0.018 — same as chat
    "identity_capture": 2,       # ~$0.002 — 200 max_tokens
    "memory_extract": 8,
    "email_absorb": 15,
}

#: Monthly credit allowance per plan. Replaces the old
#: ``_UNLIMITED_AI = {"business", "enterprise"}`` — nothing is unlimited now.
#: 1 credit = $0.001, so 10_000 credits = $10 of model spend.
PLAN_AI_CREDITS: dict[str, int] = {
    "starter": 1_000,       # ~$1.00  — ~55 chat messages or ~66 extractions
    "pro": 12_000,          # ~$12.00
    "business": 60_000,     # ~$60.00
    "enterprise": 250_000,  # ~$250.00
}

DEFAULT_PLAN_CREDITS = PLAN_AI_CREDITS["starter"]


class AiCreditsExhausted(AppError):
    """402 — the tenant is out of AI credits for this billing month."""

    def __init__(self, message: str, used: int, limit: int, operation: str):
        super().__init__(code="AI_CREDITS_EXHAUSTED", message=message, status_code=402)
        self.used = used
        self.limit = limit
        self.operation = operation


def tenant_key_for(user: User) -> str:
    """One tenant = one org, or one solo user. Mirrors resolve_org_id()."""
    if getattr(user, "org_id", None) is not None:
        return str(user.org_id)
    return str(user.id)


def current_period(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def operation_cost(operation: str, units: int = 1) -> int:
    """Credits for one invocation. Unknown operations are charged the chat rate
    rather than zero — a new AI call site must never be silently free."""
    per_unit = AI_OPERATION_COSTS.get(operation)
    if per_unit is None:
        logger.warning("ai_meter: unpriced operation %r — charging chat rate", operation)
        per_unit = AI_OPERATION_COSTS["chat"]
    return max(1, per_unit * max(1, units))


async def get_credit_limit(db: AsyncSession, user: User) -> int:
    from app.billing.limits import get_plan_key

    plan = await get_plan_key(db, user)
    return PLAN_AI_CREDITS.get(plan, DEFAULT_PLAN_CREDITS)


async def _get_or_create_row(db: AsyncSession, tenant: str, period: str) -> AiUsage:
    result = await db.execute(
        select(AiUsage).where(AiUsage.tenant_key == tenant, AiUsage.period == period)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = AiUsage(tenant_key=tenant, period=period, credits_used=0, call_count=0)
        db.add(row)
        try:
            await db.commit()
        except Exception:  # noqa: BLE001 — lost a race; the other writer won
            await db.rollback()
            result = await db.execute(
                select(AiUsage).where(AiUsage.tenant_key == tenant, AiUsage.period == period)
            )
            row = result.scalar_one()
        else:
            await db.refresh(row)
    return row


async def get_usage(db: AsyncSession, user: User) -> dict:
    """Remaining-credits view for the billing UI and platform admin."""
    tenant = tenant_key_for(user)
    period = current_period()
    row = await _get_or_create_row(db, tenant, period)
    limit = await get_credit_limit(db, user)
    used = row.credits_used or 0
    return {
        "period": period,
        "credits_used": used,
        "credits_limit": limit,
        "credits_remaining": max(0, limit - used),
        "calls": row.call_count or 0,
        "estimated_spend_usd": round(used / 1000.0, 3),
        "percent_used": round(min(100.0, (used / limit) * 100), 1) if limit else 0.0,
    }


async def consume(
    db: AsyncSession,
    user: User,
    operation: str,
    *,
    units: int = 1,
    dry_run: bool = False,
) -> int:
    """Charge one AI invocation. Raises :class:`AiCreditsExhausted` (402) when
    the tenant has no room left.

    Call this *before* the model call, not after — the point is to prevent the
    spend, not to record it once it has happened.

    Returns the credits charged.
    """
    cost = operation_cost(operation, units)
    tenant = tenant_key_for(user)
    period = current_period()

    row = await _get_or_create_row(db, tenant, period)
    limit = await get_credit_limit(db, user)
    used = row.credits_used or 0

    if used + cost > limit:
        raise AiCreditsExhausted(
            f"Your plan includes {limit / 1000:.2f} of AI usage per month and you have used "
            f"{used / 1000:.2f}. Upgrade your plan for more AI.",
            used=used, limit=limit, operation=operation,
        )

    if dry_run:
        return cost

    # Atomic increment — never read-modify-write, or concurrent AI calls lose
    # charges against each other.
    await db.execute(
        update(AiUsage)
        .where(AiUsage.tenant_key == tenant, AiUsage.period == period)
        .values(credits_used=AiUsage.credits_used + cost, call_count=AiUsage.call_count + 1)
    )
    await db.commit()
    return cost


async def safe_consume(db: AsyncSession, user: User, operation: str, *, units: int = 1) -> bool:
    """For BACKGROUND jobs: charge if there is room, otherwise skip the work.

    A scheduled job must not raise a 402 at nobody — it should just not spend.
    Returns True when the caller may proceed.
    """
    try:
        await consume(db, user, operation, units=units)
        return True
    except AiCreditsExhausted:
        logger.info("ai_meter: skipping %s for tenant %s — no credits", operation, tenant_key_for(user))
        return False
    except Exception:  # noqa: BLE001 — metering must never break the job
        logger.exception("ai_meter: consume failed for %s", operation)
        return True


async def safe_consume_by_user_id(
    db: AsyncSession, user_id, operation: str, *, units: int = 1
) -> bool:
    """:func:`safe_consume` for background jobs that only carry a user id.

    If the user cannot be loaded we allow the work rather than block it — an
    orphaned job should not be silently dropped — but that is logged, because
    an unmeterable AI call is a hole in the ceiling.
    """
    user = await db.get(User, user_id)
    if user is None:
        logger.warning("ai_meter: cannot meter %s — user %s not found", operation, user_id)
        return True
    return await safe_consume(db, user, operation, units=units)
