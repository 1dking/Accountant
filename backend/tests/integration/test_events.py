"""OBRAIN_EVENT_SPEC.md §6 step 1 — payment_processed + active_client_snapshot.

Covers: envelope dedup, the real payment code paths that now emit
payment_processed (manual invoice payment + proposal payment-on-signing),
the active_client_snapshot job's "active" definition, and the operator-only
router (auth gate + aggregate shape).
"""
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.contacts.models import ActivityType, ContactActivity
from app.events import router as events_router
from app.events.models import Event
from app.events.service import (
    emit_event,
    get_value_metrics,
    resolve_org_id,
    snapshot_active_clients,
)
from app.invoicing.schemas import InvoicePaymentCreate
from app.invoicing.service import record_payment
from app.platform_admin.router import require_platform_admin
from app.proposals.models import Proposal, ProposalStatus
from app.proposals.service import handle_proposal_payment_webhook


# ---------------------------------------------------------------------------
# emit_event: envelope + dedup
# ---------------------------------------------------------------------------

class TestEmitEvent:
    async def test_emits_and_reads_back(self, db, admin_user):
        ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        row = await emit_event(
            db, event="payment_processed", org_id=resolve_org_id(admin_user),
            properties={"amountUSD": 42.5, "source": "invoice"}, timestamp=ts,
        )
        assert row is not None
        assert row.event == "payment_processed"
        assert json.loads(row.properties_json) == {"amountUSD": 42.5, "source": "invoice"}

    async def test_identical_envelope_deduplicates(self, db, admin_user):
        """At-least-once delivery must not double-count — same event/org/
        timestamp/properties written twice yields one row (spec §1)."""
        ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        kwargs = dict(
            event="payment_processed", org_id=resolve_org_id(admin_user),
            properties={"amountUSD": 100.0, "source": "invoice"}, timestamp=ts,
        )
        first = await emit_event(db, **kwargs)
        second = await emit_event(db, **kwargs)
        assert first is not None
        assert second is None  # no-op, not an error

        count = await db.execute(select(Event).where(Event.event == "payment_processed"))
        assert len(count.scalars().all()) == 1

    async def test_dedupe_collision_does_not_expire_callers_loaded_objects(
        self, db, admin_user, sample_invoice
    ):
        """A duplicate envelope used to roll back the WHOLE session (not just
        the failed insert), expiring every other object the caller had
        loaded. In production this surfaced as a MissingGreenlet crash right
        after emit_event returned, the moment the caller's code touched an
        already-loaded attribute on an object it assumed was still fine —
        see test_cumulative_payments_mark_paid, which hit this whenever two
        equal-amount same-day payments produced identical dedupe keys.
        """
        ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        kwargs = dict(
            event="payment_processed", org_id=resolve_org_id(admin_user),
            properties={"amountUSD": 750.0, "source": "invoice"}, timestamp=ts,
        )
        # Load an attribute now, before the collision, so we can prove it
        # survives untouched — not just that a fresh reload would work.
        _ = sample_invoice.contact_id

        first = await emit_event(db, **kwargs)
        assert first is not None
        second = await emit_event(db, **kwargs)  # identical envelope -> collision
        assert second is None

        # Must not require a DB round-trip (would raise MissingGreenlet
        # outside an awaited context if the object had been expired).
        assert sample_invoice.contact_id is not None

    async def test_different_properties_do_not_collide(self, db, admin_user):
        ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        org = resolve_org_id(admin_user)
        await emit_event(db, event="payment_processed", org_id=org, properties={"amountUSD": 10.0, "source": "invoice"}, timestamp=ts)
        await emit_event(db, event="payment_processed", org_id=org, properties={"amountUSD": 20.0, "source": "invoice"}, timestamp=ts)
        count = await db.execute(select(Event).where(Event.event == "payment_processed"))
        assert len(count.scalars().all()) == 2

    def test_resolve_org_id_prefers_org_id_then_falls_back_to_user_id(self, admin_user):
        # This deployment's admin_user fixture has no org_id set.
        assert admin_user.org_id is None
        assert resolve_org_id(admin_user) == str(admin_user.id)


# ---------------------------------------------------------------------------
# Real payment code paths emit payment_processed
# ---------------------------------------------------------------------------

class TestPaymentProcessedHooks:
    async def test_record_payment_emits_event(self, db, admin_user, sample_invoice):
        await record_payment(
            db, sample_invoice.id,
            InvoicePaymentCreate(amount=Decimal("1650.00"), date=date(2026, 6, 1), payment_method="bank_transfer"),
            admin_user,
        )
        result = await db.execute(select(Event).where(Event.event == "payment_processed"))
        rows = result.scalars().all()
        assert len(rows) == 1
        props = json.loads(rows[0].properties_json)
        assert props == {"amountUSD": 1650.0, "source": "invoice"}
        assert rows[0].org_id == resolve_org_id(admin_user)
        # Honors the payment's own (possibly backdated) date, not "now".
        assert rows[0].timestamp.date() == date(2026, 6, 1)

    async def test_partial_payment_still_emits(self, db, admin_user, sample_invoice):
        """payment_processed fires on the payment itself, independent of
        whether it flips the invoice to PAID or PARTIALLY_PAID — GMV is GMV."""
        await record_payment(
            db, sample_invoice.id,
            InvoicePaymentCreate(amount=Decimal("500.00"), date=date(2026, 6, 1), payment_method="bank_transfer"),
            admin_user,
        )
        result = await db.execute(select(Event).where(Event.event == "payment_processed"))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert json.loads(rows[0].properties_json)["amountUSD"] == 500.0

    async def test_proposal_payment_webhook_emits_event(self, db, admin_user, sample_contact):
        proposal = Proposal(
            id=uuid.uuid4(), proposal_number="PRO-TEST-1", contact_id=sample_contact.id,
            title="Test Engagement", content_json="{}", status=ProposalStatus.SIGNED,
            value=Decimal("3000.00"), currency="USD", created_by=admin_user.id,
        )
        db.add(proposal)
        await db.commit()

        await handle_proposal_payment_webhook(db, proposal_id_str=str(proposal.id), payment_intent_id="pi_test123")

        result = await db.execute(select(Event).where(Event.event == "payment_processed"))
        rows = result.scalars().all()
        assert len(rows) == 1
        props = json.loads(rows[0].properties_json)
        assert props == {"amountUSD": 3000.0, "source": "proposal"}
        assert rows[0].org_id == resolve_org_id(admin_user)

    async def test_value_metrics_aggregates_gmv_by_month(self, db, admin_user, sample_invoice):
        """End-to-end: a real payment shows up as paymentsProcessedUSD in
        getValueMetrics() — this is what OBrainAdapter serves to the Lab."""
        await record_payment(
            db, sample_invoice.id,
            InvoicePaymentCreate(amount=Decimal("1650.00"), date=date(2026, 6, 15), payment_method="bank_transfer"),
            admin_user,
        )
        rows = await get_value_metrics(db)
        assert len(rows) == 1
        assert rows[0]["orgId"] == resolve_org_id(admin_user)
        assert rows[0]["month"] == "2026-06"
        assert rows[0]["paymentsProcessedUSD"] == 1650.0


# ---------------------------------------------------------------------------
# active_client_snapshot — the "active" definition
# ---------------------------------------------------------------------------

class TestActiveClientSnapshot:
    async def test_counts_contact_with_recent_activity(self, db, admin_user, sample_contact):
        db.add(ContactActivity(
            id=uuid.uuid4(), contact_id=sample_contact.id, activity_type=ActivityType.NOTE_ADDED,
            title="Called about renewal", created_by=admin_user.id,
        ))
        await db.commit()

        now = datetime(2026, 7, 1, tzinfo=timezone.utc)
        count = await snapshot_active_clients(db, now=now)
        assert count == 1

        result = await db.execute(select(Event).where(Event.event == "active_client_snapshot"))
        rows = {json.loads(r.properties_json)["window"]: json.loads(r.properties_json)["activeClients"] for r in result.scalars().all()}
        assert rows == {30: 1, 90: 1}

    async def test_activity_outside_window_not_counted(self, db, admin_user, sample_contact):
        stale = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add(ContactActivity(
            id=uuid.uuid4(), contact_id=sample_contact.id, activity_type=ActivityType.NOTE_ADDED,
            title="Old note", created_by=admin_user.id, created_at=stale,
        ))
        await db.commit()

        now = datetime(2026, 7, 1, tzinfo=timezone.utc)
        await snapshot_active_clients(db, now=now)
        result = await db.execute(select(Event).where(Event.event == "active_client_snapshot"))
        rows = {json.loads(r.properties_json)["window"]: json.loads(r.properties_json)["activeClients"] for r in result.scalars().all()}
        assert rows == {30: 0, 90: 0}

    async def test_paid_invoice_counts_as_active_without_contact_activity(self, db, admin_user, sample_invoice):
        """A contact who only ever paid an invoice (no logged ContactActivity)
        must still count as active — payment IS activity."""
        await record_payment(
            db, sample_invoice.id,
            InvoicePaymentCreate(amount=Decimal("1650.00"), date=date(2026, 6, 20), payment_method="bank_transfer"),
            admin_user,
        )
        now = datetime(2026, 7, 1, tzinfo=timezone.utc)
        await snapshot_active_clients(db, now=now)
        result = await db.execute(select(Event).where(Event.event == "active_client_snapshot"))
        rows = {json.loads(r.properties_json)["window"]: json.loads(r.properties_json)["activeClients"] for r in result.scalars().all()}
        assert rows[30] == 1


# ---------------------------------------------------------------------------
# Router: operator-only gate + aggregate shape
#
# NOTE: these deliberately do NOT use the `client`/`app` fixtures. Booting the
# full app (create_app() -> app.documents.router -> app.documents.service ->
# python-magic) crashes this Windows dev environment with a hard native
# access violation in libmagic's DLL loader on first import in a pytest
# worker — a pre-existing environment issue (confirmed unrelated to this
# change: reproduces from an empty diagnostic pytest run against main on this
# machine) — not something this PR should try to fix. The router/auth logic
# itself was verified end-to-end over real HTTP against the live dev server:
# no-auth -> 401, team_member -> 403, admin -> 200 with correct aggregate
# shape, for all four endpoints. These tests cover the same logic at the
# function level so it's still exercised by `pytest`, just without booting
# the app that crashes.
# ---------------------------------------------------------------------------

class _FakeApp:
    def __init__(self, settings):
        from types import SimpleNamespace
        self.state = SimpleNamespace(settings=settings)


class _FakeRequest:
    def __init__(self, settings):
        self.app = _FakeApp(settings)


class TestPlatformAdminGate:
    async def test_admin_role_allowed(self, admin_user):
        from tests.conftest import TEST_SETTINGS
        result = await require_platform_admin(_FakeRequest(TEST_SETTINGS), admin_user)
        assert result is admin_user

    async def test_non_admin_role_rejected(self, team_member_user):
        from tests.conftest import TEST_SETTINGS
        with pytest.raises(HTTPException) as exc_info:
            await require_platform_admin(_FakeRequest(TEST_SETTINGS), team_member_user)
        assert exc_info.value.status_code == 403

    async def test_super_admin_email_allowed_even_without_admin_role(self, team_member_user):
        from tests.conftest import TEST_SETTINGS
        settings = TEST_SETTINGS.model_copy(update={"super_admin_emails": team_member_user.email})
        result = await require_platform_admin(_FakeRequest(settings), team_member_user)
        assert result is team_member_user


class TestEventsRouterEndpoints:
    """Calls the router's endpoint functions directly — same code the HTTP
    layer invokes after its Depends() chain resolves, verified separately
    above and via manual curl against the live server."""

    async def test_accounts_shape(self, db, admin_user):
        result = await events_router.accounts(admin_user, db)
        assert result == {"data": []}

    async def test_value_metrics_reflects_real_payment(self, db, admin_user, sample_invoice):
        await record_payment(
            db, sample_invoice.id,
            InvoicePaymentCreate(amount=Decimal("1650.00"), date=date(2026, 6, 15), payment_method="bank_transfer"),
            admin_user,
        )
        result = await events_router.value_metrics(admin_user, db)
        assert len(result["data"]) == 1
        assert result["data"][0]["paymentsProcessedUSD"] == 1650.0
        assert result["data"][0]["month"] == "2026-06"

    async def test_lifecycle_and_module_usage_shape(self, db, admin_user):
        assert await events_router.lifecycle_events(admin_user, db) == {"data": []}
        assert await events_router.module_usage(admin_user, db) == {"data": []}
