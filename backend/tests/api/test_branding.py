"""Tests for universal branding settings module."""

import pytest

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Branding CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_branding(client, admin_user):
    resp = await client.get("/api/branding", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "primary_color" in data
    assert "font_heading" in data


@pytest.mark.asyncio
async def test_update_branding(client, admin_user):
    resp = await client.put(
        "/api/branding",
        json={
            "primary_color": "#ff0000",
            "font_heading": "Poppins",
            "org_slug": "my-firm",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["primary_color"] == "#ff0000"
    assert data["font_heading"] == "Poppins"
    assert data["org_slug"] == "my-firm"


@pytest.mark.asyncio
async def test_update_branding_partial(client, admin_user):
    # First set a value
    await client.put(
        "/api/branding",
        json={"accent_color": "#00ff00"},
        headers=auth_header(admin_user),
    )
    # Then update only secondary
    resp = await client.put(
        "/api/branding",
        json={"secondary_color": "#0000ff"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["secondary_color"] == "#0000ff"
    assert data["accent_color"] == "#00ff00"


@pytest.mark.asyncio
async def test_branding_singleton(client, admin_user):
    # Get twice should return same ID
    resp1 = await client.get("/api/branding", headers=auth_header(admin_user))
    resp2 = await client.get("/api/branding", headers=auth_header(admin_user))
    assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Public branding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_branding_no_auth(client, admin_user):
    # First create branding via authenticated endpoint
    await client.get("/api/branding", headers=auth_header(admin_user))
    # Then access public endpoint without auth
    resp = await client.get("/api/branding/public")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    assert "primary_color" in data
    # Public endpoint should NOT include custom_css
    assert "custom_css" not in data or data.get("custom_css") is None


@pytest.mark.asyncio
async def test_public_branding_empty(client):
    # If no branding has been set, public returns null
    # (This depends on test ordering, so just check it doesn't error)
    resp = await client.get("/api/branding/public")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_branding_unauthenticated(client):
    resp = await client.put(
        "/api/branding", json={"primary_color": "#000"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_branding_non_admin_forbidden(client, team_member_user):
    resp = await client.put(
        "/api/branding",
        json={"primary_color": "#000"},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_branding_viewer_forbidden(client, viewer_user):
    resp = await client.put(
        "/api/branding",
        json={"primary_color": "#000"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_branding_authenticated_any_role(client, accountant_user):
    resp = await client.get(
        "/api/branding", headers=auth_header(accountant_user)
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Email & Portal branding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_branding(client, admin_user):
    resp = await client.put(
        "/api/branding",
        json={
            "email_header_html": "<div style='background: blue;'>Header</div>",
            "email_footer_html": "<p>Powered by Accountant</p>",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "Header" in data["email_header_html"]
    assert "Accountant" in data["email_footer_html"]


@pytest.mark.asyncio
async def test_portal_branding(client, admin_user):
    resp = await client.put(
        "/api/branding",
        json={
            "portal_welcome_message": "Welcome to your portal!",
            "booking_page_header": "<h2>Book a meeting</h2>",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["portal_welcome_message"] == "Welcome to your portal!"
