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
