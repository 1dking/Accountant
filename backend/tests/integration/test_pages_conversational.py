"""Pages v2 conversational generation pipeline — state machine +
hybrid provider orchestration (Gemini primary → Claude → static) +
section refinement.

The underlying AI calls are stubbed so tests don't burn API credits
or require network. We're testing:
  - session lifecycle (drafting → approved → generating → complete)
  - hybrid PRD generation: Gemini wins when available
  - hybrid PRD: falls through to Claude when Gemini fails
  - hybrid PRD: falls through to static when both fail
  - section regenerate replaces a single section's jsx_content in
    sections_json without disturbing others
  - template library endpoint registered
"""
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User
from app.pages import conversational
from app.pages.models import Page, PageGenerationSession, PageStatus
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _patch_settings_keys(monkeypatch, app, *, gemini: str = "k-gem", anthropic: str = "k-ant"):
    """Force app.state.settings to have the keys we want. Without these,
    the hybrid path skips a provider entirely (empty key → skipped)."""
    monkeypatch.setattr(app.state.settings, "gemini_api_key", gemini)
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", anthropic)


def _valid_prd(title: str = "Acme Accounting") -> dict:
    return {
        "title": title,
        "audience": "Small-business owners in Ontario",
        "goals": ["book a discovery call", "build trust"],
        "sections": [
            {"id": "hero", "type": "hero", "title": "Welcome",
             "summary": "Top fold", "content_brief": "Bold headline + CTA"},
            {"id": "features", "type": "features", "title": "What we do",
             "summary": "3 cards", "content_brief": "Services list"},
        ],
    }


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_generation_session_create(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """POST /ai/sessions creates a session in drafting state."""
    resp = await client.post(
        "/api/pages/ai/sessions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "drafting"
    assert data["prompt_history"] == []
    assert data["prd"] is None
    assert data["page_id"] is None


# ---------------------------------------------------------------------------
# Hybrid provider behavior — PRD
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_prd_uses_gemini_when_available(
    client: AsyncClient, admin_user: User, app, monkeypatch
):
    """Happy path: Gemini key is set + Gemini returns a valid PRD →
    Claude is NOT called. PRD reflects Gemini's response."""
    _patch_settings_keys(monkeypatch, app)

    gemini_calls = {"n": 0}
    claude_calls = {"n": 0}

    async def _fake_gemini(*, api_key, model, system_prompt, user_msg, max_tokens, timeout):
        gemini_calls["n"] += 1
        return _valid_prd(title="From Gemini")

    async def _fake_claude(*, settings, model, system_prompt, user_msg, max_tokens, timeout):
        claude_calls["n"] += 1
        return _valid_prd(title="From Claude")

    monkeypatch.setattr(conversational, "_gemini_call_json", _fake_gemini)
    monkeypatch.setattr(conversational, "_claude_call_json", _fake_claude)

    r1 = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    session_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "Build a landing page"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["status"] == "drafting"
    assert data["prd"]["title"] == "From Gemini"
    assert gemini_calls["n"] == 1
    assert claude_calls["n"] == 0


@pytest.mark.high
async def test_prd_falls_back_to_claude_on_gemini_failure(
    client: AsyncClient, admin_user: User, app, monkeypatch
):
    """When Gemini raises, Claude is invoked and its response is used."""
    _patch_settings_keys(monkeypatch, app)

    claude_calls = {"n": 0}

    async def _fake_gemini(**kwargs):
        raise RuntimeError("gemini quota exceeded")

    async def _fake_claude(*, settings, model, system_prompt, user_msg, max_tokens, timeout):
        claude_calls["n"] += 1
        return _valid_prd(title="From Claude Fallback")

    monkeypatch.setattr(conversational, "_gemini_call_json", _fake_gemini)
    monkeypatch.setattr(conversational, "_claude_call_json", _fake_claude)

    r1 = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    session_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "Build something"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["prd"]["title"] == "From Claude Fallback"
    assert claude_calls["n"] == 1


@pytest.mark.high
async def test_prd_falls_back_to_static_when_both_providers_fail(
    client: AsyncClient, admin_user: User, app, monkeypatch
):
    """If Gemini AND Claude both fail, the static template fires so the
    endpoint never 500s and the user gets a usable page skeleton."""
    _patch_settings_keys(monkeypatch, app)

    async def _fail(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(conversational, "_gemini_call_json", _fail)
    monkeypatch.setattr(conversational, "_claude_call_json", _fail)

    r1 = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    session_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "Landing page for a coffee shop"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    # Static fallback always has 5 sections including hero + cta + footer
    section_types = {s["type"] for s in data["prd"]["sections"]}
    assert "hero" in section_types
    assert "cta" in section_types
    assert "footer" in section_types
    assert data["status"] == "drafting"
    # Provider label captured in history
    assistant_turn = next(t for t in data["prompt_history"] if t["role"] == "assistant")
    assert assistant_turn["provider"] == "static_fallback"


@pytest.mark.high
async def test_prd_invalid_shape_from_gemini_triggers_claude_fallback(
    client: AsyncClient, admin_user: User, app, monkeypatch
):
    """Gemini returns *something* but the shape validator rejects it
    (e.g., missing sections array). The hybrid skips to Claude."""
    _patch_settings_keys(monkeypatch, app)

    claude_calls = {"n": 0}

    async def _fake_gemini(**kwargs):
        return {"title": "Half-baked", "sections": []}  # invalid: empty

    async def _fake_claude(**kwargs):
        claude_calls["n"] += 1
        return _valid_prd(title="Claude Saves The Day")

    monkeypatch.setattr(conversational, "_gemini_call_json", _fake_gemini)
    monkeypatch.setattr(conversational, "_claude_call_json", _fake_claude)

    r1 = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    session_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "anything"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["prd"]["title"] == "Claude Saves The Day"
    assert claude_calls["n"] == 1


# ---------------------------------------------------------------------------
# Section refinement — uses the same hybrid stack
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_section_regenerate_isolated(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    app,
    monkeypatch,
):
    """Refining section index 1 of a 3-section page replaces only that
    section's jsx_content. Indexes 0 and 2 stay unchanged. Hybrid stack
    used (Gemini wins here)."""
    _patch_settings_keys(monkeypatch, app)

    page = Page(
        id=uuid.uuid4(),
        title="Test Page",
        slug="test-page-abc123",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {"id": "hero", "type": "hero", "title": "H",
             "jsx_content": "<section>ORIGINAL HERO</section>",
             "metadata": {}},
            {"id": "features", "type": "features", "title": "F",
             "jsx_content": "<section>ORIGINAL FEATURES</section>",
             "metadata": {}},
            {"id": "cta", "type": "cta", "title": "C",
             "jsx_content": "<section>ORIGINAL CTA</section>",
             "metadata": {}},
        ]),
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    async def _fake_gemini(**kwargs):
        return {
            "jsx_content": "<section>REFINED FEATURES</section>",
            "metadata": {"headline": "Refined"},
        }

    monkeypatch.setattr(conversational, "_gemini_call_json", _fake_gemini)

    resp = await client.post(
        f"/api/pages/{page.id}/sections/1/refine",
        json={"instruction": "Make features more concise"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    async with factory() as fresh:
        row = await fresh.execute(select(Page).where(Page.id == page.id))
        updated = row.scalar_one()
        sections = json.loads(updated.sections_json)
        assert sections[0]["jsx_content"] == "<section>ORIGINAL HERO</section>"
        assert sections[1]["jsx_content"] == "<section>REFINED FEATURES</section>"
        assert sections[1]["metadata"]["headline"] == "Refined"
        assert sections[1]["metadata"]["provider"] == "gemini"
        assert sections[2]["jsx_content"] == "<section>ORIGINAL CTA</section>"


# ---------------------------------------------------------------------------
# Misc — route registration sanity
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_template_library_endpoint_registered(app):
    """POST /api/pages/templates/generate-library is wired to the router."""
    paths = {
        getattr(r, "path", None): getattr(r, "methods", set())
        for r in app.routes
    }
    target = "/api/pages/templates/generate-library"
    assert target in paths, f"{target} not registered in app.routes"
    assert "POST" in paths[target]
