"""Telephony rate card — what a unit costs us, and what we charge for it.

Every telephony unit has two numbers: ``our_cost`` (what Twilio bills us) and
``sell_price`` (what the tenant pays). Sell price is either pinned per unit or
derived from a markup multiplier, so an operator can run a blanket 2.5x and
still hand-price the units that matter.

Resolution is most-specific-wins::

    tenant override  ->  plan override  ->  global unit row  ->  global markup

A disabled row at any level switches the unit off for that scope, which is how
"Pro does not get telephony" is expressed without special-casing plans in code.

All money is integer micro-dollars (1e-6 USD); see models.MICROS_PER_USD.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import MICROS_PER_USD, TelephonyRate
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

#: Every billable telephony unit. Keys are stable — they appear in the ledger,
#: the admin UI and cost-model.json.
UNITS: dict[str, str] = {
    "number_monthly": "Phone number (per number, per month)",
    "voice_inbound_min": "Inbound voice (per minute)",
    "voice_outbound_min": "Outbound voice (per minute)",
    "sms_inbound": "Inbound SMS (per segment)",
    "sms_outbound": "Outbound SMS (per segment)",
    "mms_inbound": "Inbound MMS (per message)",
    "mms_outbound": "Outbound MMS (per message)",
    "recording_storage_min": "Call recording storage (per minute, per month)",
    "transcription_min": "Voicemail transcription (per minute)",
    "a2p_brand": "A2P 10DLC brand registration (one-off)",
    "a2p_campaign": "A2P 10DLC campaign registration (one-off)",
    "a2p_campaign_monthly": "A2P 10DLC campaign (per month)",
}

#: Our list-price cost per unit, in micro-dollars. Seeded into the rate card on
#: first use. These are ESTIMATES from COST_LEDGER.md — an operator should
#: reconcile them against a real Twilio invoice, which is exactly why the
#: metering job records actual cost alongside them.
DEFAULT_COST_MICROS: dict[str, int] = {
    "number_monthly": 1_150_000,      # $1.15
    "voice_inbound_min": 8_500,       # $0.0085
    "voice_outbound_min": 14_000,     # $0.014
    "sms_inbound": 7_500,             # $0.0075
    "sms_outbound": 7_900,            # $0.0079
    "mms_inbound": 10_000,            # $0.01
    "mms_outbound": 20_000,           # $0.02
    "recording_storage_min": 500,     # $0.0005
    "transcription_min": 6_000,       # $0.006
    "a2p_brand": 4_000_000,           # $4.00 one-off
    "a2p_campaign": 15_000_000,       # $15.00 one-off
    "a2p_campaign_monthly": 2_000_000,  # $2.00/mo
}

#: Blanket markup applied when a unit has no pinned sell price.
DEFAULT_MARKUP = 2.5

#: Plans that get no telephony at all. A tenant on one of these resolves to a
#: disabled rate for every unit.
PLANS_WITHOUT_TELEPHONY: set[str] = {"starter"}


class TelephonyNotAvailable(AppError):
    """403 — this tenant's plan does not include telephony."""

    def __init__(self, plan_key: str, unit: str):
        super().__init__(
            code="TELEPHONY_NOT_AVAILABLE",
            message=(
                f"Telephony is not included in the {plan_key.title()} plan. "
                "Upgrade to add phone numbers, calls and SMS."
            ),
            status_code=403,
        )
        self.plan_key = plan_key
        self.unit = unit


@dataclass(frozen=True)
class ResolvedRate:
    """The effective price of one unit for one tenant."""

    unit: str
    our_cost_micros: int
    sell_price_micros: int
    is_enabled: bool
    source: str  # "tenant" | "plan" | "global" | "markup-default"
    markup_applied: float | None = None

    @property
    def margin_micros(self) -> int:
        return self.sell_price_micros - self.our_cost_micros

    @property
    def margin_pct(self) -> float:
        if self.sell_price_micros <= 0:
            return 0.0
        return round((self.margin_micros / self.sell_price_micros) * 100, 1)


def usd(micros: int) -> float:
    """Micro-dollars -> dollars, for API responses only."""
    return round(micros / MICROS_PER_USD, 6)


def to_micros(dollars: float) -> int:
    return int(round(float(dollars) * MICROS_PER_USD))


def _derive_sell(cost_micros: int, row: TelephonyRate | None, fallback_markup: float) -> tuple[int, float | None]:
    """Pinned sell price wins; otherwise cost x markup."""
    if row is not None and row.sell_price_micros is not None:
        return row.sell_price_micros, None
    markup = (row.markup_multiplier if row is not None and row.markup_multiplier else None) or fallback_markup
    return int(round(cost_micros * markup)), markup


async def _row(db: AsyncSession, scope: str, scope_key: str | None, unit: str) -> TelephonyRate | None:
    result = await db.execute(
        select(TelephonyRate).where(
            TelephonyRate.scope == scope,
            TelephonyRate.scope_key == scope_key,
            TelephonyRate.unit == unit,
        )
    )
    return result.scalar_one_or_none()


async def global_markup(db: AsyncSession) -> float:
    """The blanket multiplier, overridable from platform admin settings."""
    from app.platform_admin.service import list_platform_settings

    try:
        rows = await list_platform_settings(db, "telephony")
        for r in rows:
            if r.key == "telephony_markup_multiplier" and r.value:
                return float(r.value)
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_MARKUP


async def resolve_rate(
    db: AsyncSession, unit: str, *, tenant_key: str | None = None, plan_key: str | None = None
) -> ResolvedRate:
    """Effective rate for one unit, honouring tenant > plan > global > markup."""
    if unit not in UNITS:
        raise ValueError(f"Unknown telephony unit: {unit}")

    markup = await global_markup(db)
    global_row = await _row(db, "global", None, unit)
    base_cost = global_row.our_cost_micros if global_row else DEFAULT_COST_MICROS.get(unit, 0)

    # Most specific first.
    for scope, key, label in (
        ("tenant", tenant_key, "tenant"),
        ("plan", plan_key, "plan"),
    ):
        if not key:
            continue
        row = await _row(db, scope, key, unit)
        if row is None:
            continue
        cost = row.our_cost_micros or base_cost
        sell, applied = _derive_sell(cost, row, markup)
        return ResolvedRate(unit, cost, sell, row.is_enabled, label, applied)

    # Plans with telephony switched off entirely, unless a row above re-enabled it.
    if plan_key and plan_key in PLANS_WITHOUT_TELEPHONY:
        sell, applied = _derive_sell(base_cost, global_row, markup)
        return ResolvedRate(unit, base_cost, sell, False, "plan-default", applied)

    if global_row is not None:
        sell, applied = _derive_sell(base_cost, global_row, markup)
        return ResolvedRate(unit, base_cost, sell, global_row.is_enabled, "global", applied)

    sell, applied = _derive_sell(base_cost, None, markup)
    return ResolvedRate(unit, base_cost, sell, True, "markup-default", applied)


async def resolve_for_user(db: AsyncSession, user: User, unit: str) -> ResolvedRate:
    from app.billing.ai_meter import tenant_key_for
    from app.billing.limits import get_plan_key

    return await resolve_rate(
        db, unit, tenant_key=tenant_key_for(user), plan_key=await get_plan_key(db, user)
    )


async def require_enabled(db: AsyncSession, user: User, unit: str) -> ResolvedRate:
    """Resolve a rate and refuse if telephony is off for this tenant's plan."""
    from app.billing.limits import get_plan_key

    rate = await resolve_for_user(db, user, unit)
    if not rate.is_enabled:
        raise TelephonyNotAvailable(await get_plan_key(db, user), unit)
    return rate


async def full_card(
    db: AsyncSession, *, tenant_key: str | None = None, plan_key: str | None = None
) -> list[dict]:
    """Every unit resolved for a scope — backs the admin rate-card editor."""
    out = []
    for unit, label in UNITS.items():
        r = await resolve_rate(db, unit, tenant_key=tenant_key, plan_key=plan_key)
        out.append({
            "unit": unit,
            "label": label,
            "our_cost_usd": usd(r.our_cost_micros),
            "sell_price_usd": usd(r.sell_price_micros),
            "margin_usd": usd(r.margin_micros),
            "margin_pct": r.margin_pct,
            "is_enabled": r.is_enabled,
            "source": r.source,
            "markup_applied": r.markup_applied,
        })
    return out


async def upsert_rate(
    db: AsyncSession,
    *,
    unit: str,
    scope: str = "global",
    scope_key: str | None = None,
    our_cost_usd: float | None = None,
    sell_price_usd: float | None = None,
    markup_multiplier: float | None = None,
    is_enabled: bool | None = None,
    notes: str | None = None,
) -> TelephonyRate:
    """Create or update one rate-card row (platform admin)."""
    if unit not in UNITS:
        raise ValueError(f"Unknown telephony unit: {unit}")
    if scope not in ("global", "plan", "tenant"):
        raise ValueError(f"Unknown scope: {scope}")

    row = await _row(db, scope, scope_key, unit)
    if row is None:
        row = TelephonyRate(
            scope=scope,
            scope_key=scope_key,
            unit=unit,
            our_cost_micros=DEFAULT_COST_MICROS.get(unit, 0),
        )
        db.add(row)

    if our_cost_usd is not None:
        row.our_cost_micros = to_micros(our_cost_usd)
    if sell_price_usd is not None:
        row.sell_price_micros = to_micros(sell_price_usd)
    if markup_multiplier is not None:
        row.markup_multiplier = markup_multiplier
        # A markup and a pinned price are mutually exclusive; the newer wins.
        if sell_price_usd is None:
            row.sell_price_micros = None
    if is_enabled is not None:
        row.is_enabled = is_enabled
    if notes is not None:
        row.notes = notes

    await db.commit()
    await db.refresh(row)
    return row
