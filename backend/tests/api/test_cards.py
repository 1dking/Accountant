"""Digital business card — model, slug policy, vCard, public payload.

The card is each user's public marketing surface: get-or-create per
user, first-come slugs with a reserved-word blocklist, published-only
public access, RFC 6350 vCard download, and a server-resolved public
payload (palette fallbacks + booking URL) so the public page is one
fetch.
"""
import pytest
from httpx import AsyncClient

from app.auth.models import User
from app.cards.service import get_or_create_card
from app.cards.vcard import build_vcard
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# vCard builder
# ---------------------------------------------------------------------------


@pytest.mark.critical
def test_vcard_structure_and_escaping():
    v = build_vcard(
        display_name="Jane Q. Public",
        job_title="CEO; Founder",
        company_name="Acme, Inc.",
        email="jane@acme.com",
        phone="+1-555-0100",
        website="https://acme.com",
        card_url="https://x.io/c/jane",
    )
    assert v.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
    assert v.endswith("END:VCARD\r\n")
    assert "FN:Jane Q. Public" in v
    assert "N:Public;Jane Q.;;;" in v
    assert "ORG:Acme\\, Inc." in v          # comma escaped
    assert "TITLE:CEO\\; Founder" in v      # semicolon escaped
    assert "URL:https://x.io/c/jane" in v


# ---------------------------------------------------------------------------
# Get-or-create + editing
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_get_my_card_auto_creates(client: AsyncClient, admin_user: User):
    resp = await client.get("/api/cards/me", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["display_name"] == admin_user.full_name
    assert data["email"] == admin_user.email
    assert data["is_published"] is False
    assert data["slug"]  # generated

    # Second call returns the same card, not a duplicate
    resp2 = await client.get("/api/cards/me", headers=auth_header(admin_user))
    assert resp2.json()["data"]["id"] == data["id"]


@pytest.mark.critical
async def test_reserved_slug_rejected(client: AsyncClient, admin_user: User):
    resp = await client.put(
        "/api/cards/me", json={"slug": "admin"}, headers=auth_header(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.critical
async def test_invalid_hex_color_rejected(client: AsyncClient, admin_user: User):
    resp = await client.put(
        "/api/cards/me", json={"bg_color": "red"}, headers=auth_header(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.critical
async def test_slug_collision_rejected(client: AsyncClient, admin_user: User, accountant_user: User):
    r1 = await client.put(
        "/api/cards/me", json={"slug": "shared-slug"}, headers=auth_header(admin_user)
    )
    assert r1.status_code == 200
    r2 = await client.put(
        "/api/cards/me", json={"slug": "shared-slug"}, headers=auth_header(accountant_user)
    )
    assert r2.status_code == 422


# ---------------------------------------------------------------------------
# Public access
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unpublished_card_404s_publicly(client: AsyncClient, admin_user: User, db):
    card = await get_or_create_card(db, admin_user)
    resp = await client.get(f"/api/cards/public/{card.slug}")
    assert resp.status_code == 404


@pytest.mark.critical
async def test_published_card_public_payload(client: AsyncClient, admin_user: User, db):
    await client.put(
        "/api/cards/me",
        json={"is_published": True, "job_title": "Owner", "accent_color": "#ff0000"},
        headers=auth_header(admin_user),
    )
    card = await get_or_create_card(db, admin_user)

    resp = await client.get(f"/api/cards/public/{card.slug}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["display_name"] == admin_user.full_name
    assert data["job_title"] == "Owner"
    assert data["accent_color"] == "#ff0000"       # own value wins
    assert data["bg_color"].startswith("#")        # fallback resolved
    assert data["wallet_available"] == {"apple": False, "google": False}


@pytest.mark.critical
async def test_public_vcard_download(client: AsyncClient, admin_user: User, db):
    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)

    resp = await client.get(f"/api/cards/public/{card.slug}/vcard")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/vcard")
    assert "attachment" in resp.headers["content-disposition"]
    assert "BEGIN:VCARD" in resp.text


@pytest.mark.critical
async def test_public_manifest(client: AsyncClient, admin_user: User, db):
    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)

    resp = await client.get(f"/api/cards/public/{card.slug}/manifest")
    assert resp.status_code == 200
    manifest = resp.json()
    assert manifest["name"] == admin_user.full_name
    assert manifest["start_url"] == f"/c/{card.slug}"


@pytest.mark.high
async def test_booking_url_resolves_from_linked_calendar(
    client: AsyncClient, admin_user: User, db
):
    from app.scheduling.models import SchedulingCalendar

    cal = SchedulingCalendar(
        name="Intro Call",
        slug="intro-call-test",
        created_by=admin_user.id,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    await client.put(
        "/api/cards/me",
        json={
            "is_published": True,
            "show_booking": True,
            "scheduling_calendar_id": str(cal.id),
        },
        headers=auth_header(admin_user),
    )
    card = await get_or_create_card(db, admin_user)

    resp = await client.get(f"/api/cards/public/{card.slug}")
    assert resp.json()["data"]["booking_url"] == "/book/intro-call-test"


# ---------------------------------------------------------------------------
# Phase 6: analytics + workflow triggers + wallet endpoints
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_public_view_records_analytics(client: AsyncClient, admin_user: User, db):
    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)

    assert (await client.get(f"/api/cards/public/{card.slug}")).status_code == 200
    assert (await client.get(f"/api/cards/public/{card.slug}/vcard")).status_code == 200

    resp = await client.get("/api/cards/me/analytics", headers=auth_header(admin_user))
    assert resp.status_code == 200
    stats = resp.json()["data"]
    assert stats["total_views"] == 1
    assert stats["total_vcard_downloads"] == 1
    assert stats["unique_visitors"] == 1


@pytest.mark.critical
async def test_card_viewed_fires_workflow_with_null_contact(
    client: AsyncClient, admin_user: User, db
):
    from sqlalchemy import select

    from app.workflows.models import (
        ActionType,
        TriggerType,
        Workflow,
        WorkflowExecution,
        WorkflowStep,
    )

    workflow = Workflow(
        name="Card view alert",
        trigger_type=TriggerType.CARD_VIEWED,
        trigger_config_json="{}",
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(workflow)
    await db.flush()
    db.add(
        WorkflowStep(
            workflow_id=workflow.id,
            step_order=0,
            action_type=ActionType.SEND_NOTIFICATION,
            action_config_json='{"message": "Card viewed: {card_display_name}"}',
        )
    )
    await db.commit()

    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)
    assert (await client.get(f"/api/cards/public/{card.slug}")).status_code == 200

    executions = (
        await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow.id)
        )
    ).scalars().all()
    assert len(executions) == 1
    assert executions[0].contact_id is None


@pytest.mark.high
async def test_repeat_views_same_visitor_dedupe_dispatch_not_analytics(
    client: AsyncClient, admin_user: User, db
):
    from sqlalchemy import select

    from app.workflows.models import TriggerType, Workflow, WorkflowExecution

    workflow = Workflow(
        name="Card view dedupe",
        trigger_type=TriggerType.CARD_VIEWED,
        trigger_config_json="{}",
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(workflow)
    await db.commit()

    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)
    for _ in range(3):
        assert (await client.get(f"/api/cards/public/{card.slug}")).status_code == 200

    # Analytics stays honest: 3 raw views. Dispatch dedupes: 1 execution.
    stats = (
        await client.get("/api/cards/me/analytics", headers=auth_header(admin_user))
    ).json()["data"]
    assert stats["total_views"] == 3
    assert stats["unique_visitors"] == 1

    executions = (
        await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow.id)
        )
    ).scalars().all()
    assert len(executions) == 1


@pytest.mark.critical
async def test_vcard_download_fires_card_contact_saved(
    client: AsyncClient, admin_user: User, db
):
    from sqlalchemy import select

    from app.workflows.models import TriggerType, Workflow, WorkflowExecution

    workflow = Workflow(
        name="Contact saved alert",
        trigger_type=TriggerType.CARD_CONTACT_SAVED,
        trigger_config_json="{}",
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(workflow)
    await db.commit()

    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)
    # Unlike views, every explicit save dispatches — no dedupe window.
    assert (await client.get(f"/api/cards/public/{card.slug}/vcard")).status_code == 200
    assert (await client.get(f"/api/cards/public/{card.slug}/vcard")).status_code == 200

    executions = (
        await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow.id)
        )
    ).scalars().all()
    assert len(executions) == 2


@pytest.mark.high
async def test_wallet_endpoints_404_when_unconfigured(
    client: AsyncClient, admin_user: User, db
):
    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)

    assert (await client.get(f"/api/cards/public/{card.slug}/wallet/apple")).status_code == 404
    assert (await client.get(f"/api/cards/public/{card.slug}/wallet/google")).status_code == 404

    # And the public payload advertises neither.
    payload = (await client.get(f"/api/cards/public/{card.slug}")).json()["data"]
    assert payload["wallet_available"] == {"apple": False, "google": False}


@pytest.mark.critical
async def test_vcard_open_param_serves_inline(client: AsyncClient, admin_user: User, db):
    """?open=1 (sent by phones) must serve inline so the OS hands the
    vCard to the native Contacts UI instead of downloading a file."""
    await client.put(
        "/api/cards/me", json={"is_published": True}, headers=auth_header(admin_user)
    )
    card = await get_or_create_card(db, admin_user)

    default = await client.get(f"/api/cards/public/{card.slug}/vcard")
    assert "attachment" in default.headers["content-disposition"]

    inline = await client.get(f"/api/cards/public/{card.slug}/vcard?open=1")
    assert inline.status_code == 200
    assert "inline" in inline.headers["content-disposition"]
    assert "attachment" not in inline.headers["content-disposition"]
    assert "BEGIN:VCARD" in inline.text
