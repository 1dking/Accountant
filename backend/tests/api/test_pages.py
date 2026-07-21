"""Tests for the AI page builder module."""

import pytest
import pytest_asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
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


# ---------------------------------------------------------------------------
# AI generation is admin-only (cost control); refine/chat stay open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_generate_team_member_forbidden(client, team_member_user):
    resp = await client.post(
        "/api/pages/ai/generate",
        json={"prompt": "Create a landing page for my accounting firm"},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ai_generate_admin_allowed(client, admin_user):
    resp = await client.post(
        "/api/pages/ai/generate",
        json={"prompt": "Create a landing page for my accounting firm"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_ai_refine_team_member_not_forbidden(client, team_member_user, sample_page):
    """Refine is a per-section in-editor tool the owner wants team members to
    keep — it must not be blocked by the role gate (whatever else it returns
    depends on unrelated business logic, not tested here)."""
    resp = await client.post(
        "/api/pages/ai/refine",
        json={"page_id": sample_page["id"], "instruction": "make it punchier"},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_ai_chat_team_member_not_forbidden(client, team_member_user, sample_page):
    resp = await client.post(
        "/api/pages/ai/chat",
        json={"page_id": sample_page["id"], "message": "hello"},
        headers=auth_header(team_member_user),
    )
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Templates: sections_json round-trips through save-as-template + clone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_template_preserves_sections_json_through_clone(client, admin_user, sample_page):
    sections = '[{"id": "hero-1", "variant": "hero-centered"}]'
    resp = await client.put(
        f"/api/pages/{sample_page['id']}",
        json={
            "html_content": "<h1>Hi</h1>",
            "css_content": "h1{color:red}",
            "sections_json": sections,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sections_json"] == sections

    resp = await client.post(
        "/api/pages/templates",
        json={
            "name": "My Template",
            "scope": "org",
            "source_page_id": sample_page["id"],
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    template = resp.json()["data"]
    assert template["html_content"] == "<h1>Hi</h1>"
    assert template["sections_json"] == sections

    resp = await client.post(
        f"/api/pages/templates/{template['id']}/create-page",
        params={"title": "Cloned Page"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    cloned = resp.json()["data"]
    assert cloned["sections_json"] == sections


@pytest.mark.asyncio
async def test_create_template_with_sections_json_directly(client, admin_user):
    sections = '[{"id": "hero-1", "variant": "hero-centered"}]'
    resp = await client.post(
        "/api/pages/templates",
        json={
            "name": "Direct Template",
            "scope": "platform",
            "html_content": "<h1>x</h1>",
            "sections_json": sections,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    template = resp.json()["data"]
    assert template["sections_json"] == sections

    resp = await client.post(
        f"/api/pages/templates/{template['id']}/create-page",
        params={"title": "Cloned From Direct"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["sections_json"] == sections


# ---------------------------------------------------------------------------
# Template org-scoping: ORG templates are private to their org
# ---------------------------------------------------------------------------


async def _make_bare_user(db: AsyncSession, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=None,
        full_name=email,
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def two_orgs(db: AsyncSession):
    """Two orgs, each with its own admin — owner_id FKs to a real user, so
    the user must exist before its org, then gets org_id backfilled."""
    from app.platform_admin.models import Organization

    user_a = await _make_bare_user(db, "org-a-admin@test.com")
    user_b = await _make_bare_user(db, "org-b-admin@test.com")

    org_a = Organization(id=uuid.uuid4(), name="Org A", slug=f"org-a-{uuid.uuid4().hex[:8]}", owner_id=user_a.id)
    org_b = Organization(id=uuid.uuid4(), name="Org B", slug=f"org-b-{uuid.uuid4().hex[:8]}", owner_id=user_b.id)
    db.add_all([org_a, org_b])
    await db.commit()

    user_a.org_id = org_a.id
    user_b.org_id = org_b.id
    await db.commit()
    await db.refresh(user_a)
    await db.refresh(user_b)
    return user_a, user_b


@pytest.mark.asyncio
async def test_org_template_not_visible_to_other_org(client, two_orgs):
    user_a, user_b = two_orgs
    resp = await client.post(
        "/api/pages/templates",
        json={"name": "Org A Private", "scope": "org", "html_content": "<p>a</p>"},
        headers=auth_header(user_a),
    )
    assert resp.status_code == 201
    template_id = resp.json()["data"]["id"]

    list_resp = await client.get("/api/pages/templates", headers=auth_header(user_b))
    assert list_resp.status_code == 200
    assert all(t["id"] != template_id for t in list_resp.json()["data"])

    get_resp = await client.get(f"/api/pages/templates/{template_id}", headers=auth_header(user_b))
    assert get_resp.status_code == 404

    own_list = await client.get("/api/pages/templates", headers=auth_header(user_a))
    assert any(t["id"] == template_id for t in own_list.json()["data"])


@pytest.mark.asyncio
async def test_platform_template_visible_to_all_orgs(client, two_orgs):
    user_a, user_b = two_orgs
    resp = await client.post(
        "/api/pages/templates",
        json={"name": "Shared Platform Template", "scope": "platform", "html_content": "<p>p</p>"},
        headers=auth_header(user_a),
    )
    assert resp.status_code == 201
    template_id = resp.json()["data"]["id"]

    list_resp = await client.get("/api/pages/templates", headers=auth_header(user_b))
    assert any(t["id"] == template_id for t in list_resp.json()["data"])

    get_resp = await client.get(f"/api/pages/templates/{template_id}", headers=auth_header(user_b))
    assert get_resp.status_code == 200
