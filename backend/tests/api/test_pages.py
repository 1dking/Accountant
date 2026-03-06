"""Tests for the AI page builder module."""

import pytest
import pytest_asyncio
import uuid

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def sample_page(client, admin_user):
    resp = await client.post(
        "/api/pages",
        json={"title": "Test Landing Page", "style_preset": "modern"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Page CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_page(client, admin_user):
    resp = await client.post(
        "/api/pages",
        json={"title": "My Page", "description": "A test page"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"] == "My Page"
    assert data["slug"] == "my-page"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_list_pages(client, admin_user, sample_page):
    resp = await client.get("/api/pages", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) >= 1
    assert "meta" in data


@pytest.mark.asyncio
async def test_get_page(client, admin_user, sample_page):
    resp = await client.get(
        f"/api/pages/{sample_page['id']}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Test Landing Page"


@pytest.mark.asyncio
async def test_update_page(client, admin_user, sample_page):
    resp = await client.put(
        f"/api/pages/{sample_page['id']}",
        json={"title": "Updated Page", "html_content": "<h1>Hello</h1>"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Updated Page"


@pytest.mark.asyncio
async def test_delete_page(client, admin_user, sample_page):
    resp = await client.delete(
        f"/api/pages/{sample_page['id']}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_publish_page(client, admin_user, sample_page):
    resp = await client.post(
        f"/api/pages/{sample_page['id']}/publish",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "published"


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_versions(client, admin_user, sample_page):
    # Update to create a version
    await client.put(
        f"/api/pages/{sample_page['id']}",
        json={"html_content": "<h1>Version 1</h1>"},
        headers=auth_header(admin_user),
    )
    resp = await client.get(
        f"/api/pages/{sample_page['id']}/versions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_restore_version(client, admin_user, sample_page):
    # Create initial content
    await client.put(
        f"/api/pages/{sample_page['id']}",
        json={"html_content": "<h1>Original</h1>"},
        headers=auth_header(admin_user),
    )
    # Get version
    versions_resp = await client.get(
        f"/api/pages/{sample_page['id']}/versions",
        headers=auth_header(admin_user),
    )
    versions = versions_resp.json()["data"]
    if versions:
        version_id = versions[0]["id"]
        resp = await client.post(
            f"/api/pages/{sample_page['id']}/versions/{version_id}/restore",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_analytics(client, admin_user, sample_page):
    resp = await client.get(
        f"/api/pages/{sample_page['id']}/analytics",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_views" in data
    assert "conversion_rate" in data


# ---------------------------------------------------------------------------
# Style presets & templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_style_presets(client, admin_user):
    resp = await client.get(
        "/api/pages/style-presets", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    presets = resp.json()["data"]
    assert len(presets) >= 6
    assert any(p["id"] == "modern" for p in presets)


@pytest.mark.asyncio
async def test_section_templates(client, admin_user):
    resp = await client.get(
        "/api/pages/section-templates", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    templates = resp.json()["data"]
    assert len(templates) >= 14


# ---------------------------------------------------------------------------
# AI generate (falls back to template without API key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_generate_fallback(client, admin_user):
    resp = await client.post(
        "/api/pages/ai/generate",
        json={"prompt": "Create a landing page for my accounting firm"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert "html_content" in data
    assert "css_content" in data


# ---------------------------------------------------------------------------
# Auth & role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_page_unauthenticated(client):
    resp = await client.post("/api/pages", json={"title": "Fail"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_page_viewer_forbidden(client, viewer_user):
    resp = await client.post(
        "/api/pages",
        json={"title": "Fail"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_page_non_admin_forbidden(client, team_member_user, admin_user, sample_page):
    resp = await client.delete(
        f"/api/pages/{sample_page['id']}",
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_nonexistent_page(client, admin_user):
    resp = await client.get(
        f"/api/pages/{uuid.uuid4()}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404
