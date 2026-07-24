"""Pull Twilio usage per subaccount, rebill it, and reconcile realised margin.

Twilio is the source of truth for what we were actually charged. This job reads
each subaccount's Usage Records, converts Twilio's categories into our rate-card
units, debits the tenant's prepaid balance at OUR sell price, and stores OUR
cost on the same ledger row.

Because both numbers land together, realised margin is a query:

    SUM(billed_micros) - SUM(our_cost_micros)   per tenant, per month

which is the number that proves the markup actually works, rather than the
estimate in COST_LEDGER.md.

Idempotency: every ledger row carries the Twilio usage-record key as
``external_ref`` with a UNIQUE constraint, so re-running this job — or running
it twice concurrently — cannot double-bill.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import telephony_credits
from app.billing.models import (
    MICROS_PER_USD,
    TelephonyCredit,
    TelephonyLedgerEntry,
)
from app.billing.rate_card import resolve_rate, usd

logger = logging.getLogger(__name__)

#: Twilio usage category -> our rate-card unit. Categories we do not map are
#: ignored for BILLING but still counted in the reconciliation total, so a
#: category we forgot shows up as unbilled cost rather than vanishing.
TWILIO_CATEGORY_MAP: dict[str, str] = {
    "phonenumbers": "number_monthly",
    "phonenumbers-local": "number_monthly",
    "phonenumbers-tollfree": "number_monthly",
    "calls-inbound": "voice_inbound_min",
    "calls-outbound": "voice_outbound_min",
    "sms-inbound": "sms_inbound",
    "sms-outbound": "sms_outbound",
    "mms-inbound": "mms_inbound",
    "mms-outbound": "mms_outbound",
    "recordings": "recording_storage_min",
    "transcriptions": "transcription_min",
}

#: Twilio categories that are now debited SYNCHRONOUSLY at send/call time
#: (telephony_credits.debit_now). The daily meter must NOT charge the tenant
#: for these again, or every outbound message/call is billed twice. Their real
#: cost still surfaces in ``unmapped_cost`` for margin visibility.
LIVE_DEBITED_CATEGORIES = frozenset({"sms-outbound", "calls-outbound", "mms-outbound"})


async def meter_subaccount(
    db: AsyncSession, account, settings, *, period: str = "yesterday"
) -> dict:
    """Meter one tenant's Twilio usage for a period.

    ``period`` maps to Twilio's usage sub-resources: 'yesterday', 'today',
    'thisMonth', 'lastMonth'. The scheduler uses 'yesterday' so each day is
    metered once, after Twilio has finalised it.
    """
    from app.communication.telephony import subaccount_client

    tenant = account.tenant_key
    plan_key = None
    try:
        from app.auth.models import User
        from app.billing.limits import get_plan_key

        owner = await db.get(User, account.owner_user_id)
        if owner is not None:
            plan_key = await get_plan_key(db, owner)
    except Exception:  # noqa: BLE001 — plan lookup must not stop metering
        logger.exception("metering: could not resolve plan for %s", tenant)

    try:
        client = subaccount_client(account)
        records = getattr(client.usage.records, _period_attr(period)).list(limit=100)
    except Exception:  # noqa: BLE001
        logger.exception("metering: could not read usage for %s", account.subaccount_sid)
        return {"tenant_key": tenant, "error": "usage_read_failed"}

    billed_total = 0
    cost_total = 0
    unmapped_cost = 0
    lines = 0

    for rec in records:
        category = (getattr(rec, "category", "") or "").lower()
        qty = float(getattr(rec, "count", 0) or 0)
        actual_cost_usd = abs(float(getattr(rec, "price", 0) or 0))
        if qty <= 0 and actual_cost_usd <= 0:
            continue

        # Outbound SMS/calls are debited live at send time — metering them here
        # would double-charge. Record the actual cost for margin, don't re-bill.
        if category in LIVE_DEBITED_CATEGORIES:
            cost_total += int(round(actual_cost_usd * MICROS_PER_USD))
            continue

        unit = TWILIO_CATEGORY_MAP.get(category)
        if unit is None:
            # Real cost we are not rebilling — surfaced, never silently dropped.
            unmapped_cost += int(round(actual_cost_usd * MICROS_PER_USD))
            continue

        rate = await resolve_rate(db, unit, tenant_key=tenant, plan_key=plan_key)

        # One ledger row per (subaccount, category, period-bucket). Twilio does
        # not give a stable per-record SID on aggregates, so this composite is
        # the idempotency key.
        start = getattr(rec, "start_date", None)
        ref = f"tw:{account.subaccount_sid}:{category}:{start}"

        entry = await telephony_credits.charge(
            db, tenant,
            unit=unit,
            quantity=qty,
            rate=rate,
            external_ref=ref,
            description=f"Twilio {category} x{qty:g}",
        )
        if entry is None:
            continue  # already metered

        # Overwrite the estimated cost with Twilio's ACTUAL price. This is what
        # makes the margin figure real rather than modelled.
        if actual_cost_usd > 0:
            entry.our_cost_micros = int(round(actual_cost_usd * MICROS_PER_USD))
            await db.commit()

        billed_total += entry.billed_micros
        cost_total += entry.our_cost_micros
        lines += 1

    if unmapped_cost:
        logger.warning(
            "metering: $%.4f of unmapped Twilio cost for tenant %s — not rebilled",
            usd(unmapped_cost), tenant,
        )

    # Balance may have gone negative on observed usage; try an auto top-up.
    try:
        await telephony_credits.maybe_auto_topup(db, tenant, settings)
    except Exception:  # noqa: BLE001
        logger.exception("metering: auto top-up check failed for %s", tenant)

    await _notify_if_low(db, tenant)

    return {
        "tenant_key": tenant,
        "lines": lines,
        "billed_usd": usd(billed_total),
        "our_cost_usd": usd(cost_total),
        "margin_usd": usd(billed_total - cost_total),
        "unmapped_cost_usd": usd(unmapped_cost),
    }


def _period_attr(period: str) -> str:
    return {
        "yesterday": "yesterday",
        "today": "today",
        "thisMonth": "this_month",
        "lastMonth": "last_month",
    }.get(period, "yesterday")


async def _notify_if_low(db: AsyncSession, tenant_key: str) -> None:
    """One notification per dip below the threshold, cleared on top-up."""
    result = await db.execute(
        select(TelephonyCredit).where(TelephonyCredit.tenant_key == tenant_key)
    )
    row = result.scalar_one_or_none()
    if row is None or row.balance_micros >= telephony_credits.LOW_BALANCE_MICROS:
        return
    if row.low_balance_notified_at is not None:
        return

    try:
        from app.notifications.service import create_notification

        empty = row.balance_micros <= 0
        await create_notification(
            db,
            user_id=row.owner_user_id,
            type="telephony_credit_low",
            title="Telephony credit is empty" if empty else "Telephony credit is low",
            message=(
                "Outbound calls and texts are paused until you top up. "
                "Incoming calls and texts still work."
                if empty else
                f"Balance is ${usd(row.balance_micros):.2f}. Top up to avoid interruption."
            ),
            resource_type="telephony_credit",
            resource_id=str(row.id),
        )
        row.low_balance_notified_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("metering: low-balance notification failed for %s", tenant_key)


async def meter_all(db: AsyncSession, settings, *, period: str = "yesterday") -> dict:
    """Scheduled entry point: meter every provisioned subaccount."""
    from app.billing.models import TelephonyAccount

    rows = (await db.execute(select(TelephonyAccount))).scalars().all()
    results = []
    for account in rows:
        try:
            results.append(await meter_subaccount(db, account, settings, period=period))
        except Exception:  # noqa: BLE001 — one bad tenant must not stop the rest
            logger.exception("metering: failed for tenant %s", account.tenant_key)

    return {
        "tenants": len(results),
        "billed_usd": round(sum(r.get("billed_usd", 0) for r in results), 4),
        "our_cost_usd": round(sum(r.get("our_cost_usd", 0) for r in results), 4),
        "margin_usd": round(sum(r.get("margin_usd", 0) for r in results), 4),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Reconciliation / margin reporting
# ---------------------------------------------------------------------------


async def margin_report(db: AsyncSession, period: str | None = None) -> list[dict]:
    """Realised margin per tenant for a month — cost vs revenue, from the ledger."""
    period = period or telephony_credits.current_period()

    rows = (
        await db.execute(
            select(
                TelephonyLedgerEntry.tenant_key,
                func.sum(TelephonyLedgerEntry.our_cost_micros),
                func.sum(TelephonyLedgerEntry.billed_micros),
                func.count(),
            )
            .where(
                TelephonyLedgerEntry.period == period,
                TelephonyLedgerEntry.entry_type.in_(("usage", "a2p_fee")),
            )
            .group_by(TelephonyLedgerEntry.tenant_key)
        )
    ).all()

    out = []
    for tenant_key, cost, billed, n in rows:
        cost = int(cost or 0)
        billed = int(billed or 0)
        margin = billed - cost
        out.append({
            "tenant_key": tenant_key,
            "period": period,
            "our_cost_usd": usd(cost),
            "billed_usd": usd(billed),
            "margin_usd": usd(margin),
            "margin_pct": round((margin / billed) * 100, 1) if billed > 0 else 0.0,
            "entries": n,
            "balance_usd": usd(await telephony_credits.get_balance_micros(db, tenant_key)),
        })
    out.sort(key=lambda r: r["billed_usd"], reverse=True)
    return out
