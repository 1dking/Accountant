"""Event emission + operator-only aggregate reads, per OBRAIN_EVENT_SPEC.md.

## Honesty note on `orgId` and `mrr` (read before touching this file)

This app has no enforced multi-tenancy (see app/core/authorization.py: records
are private to their owning USER, not to a formal "org"). `User.org_id` exists
but is nullable and only used today for the opt-in shared cashbook — most
deployments have exactly one real cohort: one admin/owner and their employees.
`resolve_org_id()` below uses `User.org_id` when set, else falls back to the
owning admin's user id as a stable per-deployment cohort key.

There is also no per-org subscription/tier record anywhere in this codebase —
Platform Admin's "Pricing & Limits" is a global default price list, not a
per-org billing assignment, and Stripe here processes one-off invoice/proposal
payments, not recurring org subscriptions. That means `tier_changed` /
`trial_converted` / `mrr` (§2 of the spec) have NO existing code path to hook
— inventing one would violate "don't invent new moments." `getAccounts()` and
`getLifecycleEvents()` are implemented in full against the spec's event names
so they are ready the moment those events exist, but will legitimately return
empty/sparse data until that lifecycle work ships (spec §6 step 2). Only
`payment_processed` and `active_client_snapshot` (§6 step 1) are emitted in
this pass, from real existing payment code paths.
"""

import hashlib
import json
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.events.models import Event

# Canonical names, per spec §2-§4. Only the ones this pass actually emits are
# hooked into real code; the rest are declared here so future hooks use the
# exact spelling the adapter/scoring code expects.
LIFECYCLE_EVENTS = {
    "account_signup", "account_activated", "trial_converted",
    "tier_changed", "addon_changed", "account_churned",
}
VALUE_METRIC_EVENTS = {
    "payment_processed", "active_client_snapshot", "ai_message",
    "voice_minute", "sms_segment", "storage_snapshot", "page_published",
    "seat_snapshot",
}
MODULE_EVENTS = {"module_first_used", "module_active_snapshot"}


def resolve_org_id(user: User) -> str:
    """The event envelope's cohort key. See module docstring."""
    if user.org_id is not None:
        return str(user.org_id)
    return str(user.id)


def _json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date_type)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"not JSON serializable: {type(obj)}")


def _dedupe_key(event: str, org_id: str, timestamp: datetime, properties: dict) -> str:
    props_json = json.dumps(properties, sort_keys=True, default=_json_default)
    raw = f"{event}|{org_id}|{timestamp.isoformat()}|{props_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def emit_event(
    db: AsyncSession,
    *,
    event: str,
    org_id: str,
    properties: dict,
    timestamp: datetime | None = None,
) -> Event | None:
    """Append one event. Self-contained commit (matches log_activity's
    fire-and-forget style) so a reporting-log write never risks the caller's
    own transaction. Tolerates at-least-once delivery: returns None (no-op,
    not an error) if this exact envelope was already recorded.
    """
    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    dedupe_key = _dedupe_key(event, org_id, ts, properties)

    row = Event(
        event=event,
        org_id=org_id,
        timestamp=ts,
        properties_json=json.dumps(properties, default=_json_default),
        dedupe_key=dedupe_key,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    await db.refresh(row)
    return row


def _load(row: Event) -> dict:
    return {
        "event": row.event,
        "orgId": row.org_id,
        "timestamp": row.timestamp.isoformat(),
        "properties": json.loads(row.properties_json),
    }


# ---------------------------------------------------------------------------
# Aggregate reads — operator-only, cross-tenant. Enforced at the router layer
# (require_platform_admin), not here; these functions assume the caller has
# already authorized the request.
# ---------------------------------------------------------------------------

async def get_lifecycle_events(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Event).where(Event.event.in_(LIFECYCLE_EVENTS)).order_by(Event.timestamp)
    )
    return [_load(r) for r in result.scalars().all()]


async def get_accounts(db: AsyncSession) -> list[dict]:
    """Current-state projection folded from the lifecycle stream, per spec §2.
    Empty until lifecycle events exist (see module docstring) — that is
    correct, not a bug.
    """
    events = await get_lifecycle_events(db)
    state: dict[str, dict] = {}
    for e in events:
        org = state.setdefault(e["orgId"], {
            "orgId": e["orgId"], "tier": None, "mrr": None, "billingCycle": None,
            "status": "unknown", "activatedModules": [], "whiteLabel": False,
            "signupDate": None, "industry": None, "teamSize": None,
        })
        props = e["properties"]
        if e["event"] == "account_signup":
            org["signupDate"] = e["timestamp"]
            org["industry"] = props.get("industry")
            org["teamSize"] = props.get("teamSize")
            org["status"] = "trial"
        elif e["event"] == "account_activated":
            mods = org["activatedModules"]
            if props.get("firstModule") and props["firstModule"] not in mods:
                mods.append(props["firstModule"])
        elif e["event"] == "trial_converted":
            org["tier"] = props.get("toTier")
            org["mrr"] = props.get("mrr")
            org["status"] = "active"
        elif e["event"] == "tier_changed":
            org["tier"] = props.get("toTier")
            if org["mrr"] is not None and props.get("mrrDelta") is not None:
                org["mrr"] = org["mrr"] + props["mrrDelta"]
        elif e["event"] == "addon_changed":
            if props.get("addon") == "whiteLabel":
                org["whiteLabel"] = props.get("action") == "attach"
        elif e["event"] == "account_churned":
            org["status"] = "churned"
    return list(state.values())


async def get_value_metrics(db: AsyncSession) -> list[dict]:
    """One row per orgId per month, per spec §3: sum flow events, take the
    latest of each snapshot event within the month.
    """
    result = await db.execute(
        select(Event).where(Event.event.in_(VALUE_METRIC_EVENTS)).order_by(Event.timestamp)
    )
    rows: dict[tuple[str, str], dict] = {}

    def bucket(org_id: str, ts: datetime) -> dict:
        month = ts.strftime("%Y-%m")
        key = (org_id, month)
        if key not in rows:
            rows[key] = {
                "orgId": org_id, "month": month, "activeClients": None,
                "paymentsProcessedUSD": 0.0, "aiMessages": 0, "voiceMinutes": 0,
                "smsSegments": 0, "storageGB": None, "publishedPages": None,
                "seatsUsed": None,
            }
        return rows[key]

    for row in result.scalars().all():
        props = json.loads(row.properties_json)
        b = bucket(row.org_id, row.timestamp)
        if row.event == "payment_processed":
            b["paymentsProcessedUSD"] += float(props.get("amountUSD", 0))
        elif row.event == "active_client_snapshot":
            # Prefer the 30-day window if both exist; last snapshot wins on tie.
            if b["activeClients"] is None or props.get("window") == 30:
                b["activeClients"] = props.get("activeClients")
        elif row.event == "ai_message":
            b["aiMessages"] += int(props.get("count", 1))
        elif row.event == "voice_minute":
            b["voiceMinutes"] += int(props.get("minutes", 0))
        elif row.event == "sms_segment":
            b["smsSegments"] += int(props.get("segments", 0))
        elif row.event == "storage_snapshot":
            b["storageGB"] = props.get("gb")
        elif row.event == "page_published":
            b["publishedPages"] = props.get("totalPublished")
        elif row.event == "seat_snapshot":
            b["seatsUsed"] = props.get("seatsUsed")

    return list(rows.values())


async def get_module_usage(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Event).where(Event.event.in_(MODULE_EVENTS)).order_by(Event.timestamp)
    )
    state: dict[tuple[str, str], dict] = {}
    monthly_counts: dict[tuple[str, str], set[str]] = {}
    for row in result.scalars().all():
        props = json.loads(row.properties_json)
        if row.event == "module_first_used":
            module = props.get("module")
            key = (row.org_id, module)
            if key not in state:
                state[key] = {
                    "orgId": row.org_id, "module": module,
                    "firstUsedDate": row.timestamp.isoformat(), "monthlyActiveCount": 0,
                }
        elif row.event == "module_active_snapshot":
            month = row.timestamp.strftime("%Y-%m")
            for module in props.get("activeModules", []):
                mkey = (row.org_id, module)
                monthly_counts.setdefault(mkey, set()).add(month)
                if mkey not in state:
                    state[mkey] = {
                        "orgId": row.org_id, "module": module,
                        "firstUsedDate": None, "monthlyActiveCount": 0,
                    }
    for mkey, months in monthly_counts.items():
        state[mkey]["monthlyActiveCount"] = len(months)
    return list(state.values())


# ---------------------------------------------------------------------------
# active_client_snapshot — §6 step 1. See core/scheduler.py::_snapshot_active_clients
# for the monthly job that calls this.
# ---------------------------------------------------------------------------

async def snapshot_active_clients(db: AsyncSession, *, now: datetime | None = None) -> int:
    """For every distinct contact-book owner, count contacts with any activity
    or payment in the trailing 30/90 days and emit `active_client_snapshot`.

    "Active client" = a contact with a ContactActivity row OR a paid invoice
    (via InvoicePayment -> Invoice.contact_id) in the window. Defined once,
    here — per the spec's warning, this definition must not drift.
    """
    from app.contacts.models import Contact, ContactActivity
    from app.invoicing.models import Invoice, InvoicePayment

    now = now or datetime.now(timezone.utc)

    owners_result = await db.execute(select(Contact.created_by).distinct())
    owner_ids = [row[0] for row in owners_result.all() if row[0] is not None]

    snapshotted = 0
    for owner_id in owner_ids:
        owner = (await db.execute(select(User).where(User.id == owner_id))).scalar_one_or_none()
        if owner is None:
            continue
        org_id = resolve_org_id(owner)

        for window in (30, 90):
            cutoff = now - timedelta(days=window)

            activity_ids = await db.execute(
                select(ContactActivity.contact_id)
                .join(Contact, Contact.id == ContactActivity.contact_id)
                .where(Contact.created_by == owner_id, ContactActivity.created_at >= cutoff)
                .distinct()
            )
            payment_contact_ids = await db.execute(
                select(Invoice.contact_id)
                .join(InvoicePayment, InvoicePayment.invoice_id == Invoice.id)
                .where(Invoice.created_by == owner_id, InvoicePayment.date >= cutoff.date())
                .distinct()
            )
            active_ids = {r[0] for r in activity_ids.all()} | {r[0] for r in payment_contact_ids.all() if r[0]}

            await emit_event(
                db,
                event="active_client_snapshot",
                org_id=org_id,
                properties={"activeClients": len(active_ids), "window": window},
                timestamp=now,
            )
        snapshotted += 1

    return snapshotted
