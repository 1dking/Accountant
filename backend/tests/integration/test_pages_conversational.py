"""Pages v2 conversational generation pipeline — state machine +
planner provider order (Sonnet → Gemini → static, block model v2) +
section refinement.

The underlying AI calls are stubbed so tests don't burn API credits
or require network. We're testing:
  - session lifecycle (drafting → approved → generating → complete)
  - plan: Claude (Sonnet) wins when available; blocks come from the library
  - plan: falls through to Gemini when Claude fails
  - plan: falls through to the static plan when both fail
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
    """A planner reply (block model v2): a full-site plan with a single
    home page. The AI chooses blocks by variant_id and writes briefs —
    never markup."""
    return {
        "site_title": title,
        "audience": "Small-business owners in Ontario",
        "goals": ["book a discovery call", "build trust"],
        "pages": [{
            "path": "home", "role": "home", "title": title, "nav_label": "Home",
            "sections": [
                {"variant_id": "hero_video", "brief": "Bold headline + CTA"},
                {"variant_id": "features_3col_icon", "brief": "Services list"},
                {"variant_id": "cta_centered_banner", "brief": "Book a call"},
                {"variant_id": "footer_4col", "brief": "Links"},
            ],
        }],
    }


def _prd_title(data: dict) -> str:
    prd = data["prd"] or {}
    return prd.get("site_title") or prd.get("title") or (prd.get("pages") or [{}])[0].get("title") or ""


def _prd_home_section_types(data: dict) -> list[str]:
    prd = data["prd"] or {}
    pages = prd.get("pages") or []
    if pages:
        return [s.get("type") or s.get("category") for s in (pages[0].get("sections") or [])]
    return [s.get("type") for s in (prd.get("sections") or [])]


@pytest.fixture
async def library(db: AsyncSession):
    """A minimal active block library so the planner has something to pick."""
    from app.pages.models import SectionVariant
    from app.pages.variant_seeds import all_variants
    from app.pages.variants import _seed_values
    wanted = {"hero_video", "features_3col_icon", "cta_centered_banner", "footer_4col", "nav_centered_logo", "contact_lead_form"}
    for v in all_variants():
        if v["variant_id"] in wanted:
            db.add(SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v)))
    await db.commit()


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
# Provider order — plan (block model v2): Sonnet → Gemini → static
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_plan_uses_claude_first(
    client: AsyncClient, admin_user: User, app, library, monkeypatch
):
    """Owner rule: Sonnet plans + fills. Gemini is NOT called when Claude answers."""
    _patch_settings_keys(monkeypatch, app)
    gemini_calls = {"n": 0}
    claude_calls = {"n": 0}

    async def _fake_gemini(*, api_key, model, system_prompt, user_msg, max_tokens, timeout):
        gemini_calls["n"] += 1
        return _valid_prd(title="From Gemini")

    async def _fake_claude(*, settings, model, system_prompt, user_msg, max_tokens, timeout):
        claude_calls["n"] += 1
        # first call = plan, second = fill
        return _valid_prd(title="From Claude") if claude_calls["n"] == 1 else {"sections": {}}

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
    assert _prd_title(data) == "From Claude"
    assert [s["variant_id"] for s in data["prd"]["pages"][0]["sections"]] == ["hero_video", "features_3col_icon", "cta_centered_banner", "footer_4col"]
    assert all("jsx" not in json.dumps(s).lower() for s in data["prd"]["pages"][0]["sections"])
    assert claude_calls["n"] == 2 and gemini_calls["n"] == 0


@pytest.mark.high
async def test_plan_falls_back_to_gemini_on_claude_failure(
    client: AsyncClient, admin_user: User, app, library, monkeypatch
):
    """When Claude raises, Gemini plans (and fills)."""
    _patch_settings_keys(monkeypatch, app)
    gemini_calls = {"n": 0}

    async def _fake_claude(**kwargs):
        raise RuntimeError("anthropic overloaded")

    async def _fake_gemini(*, api_key, model, system_prompt, user_msg, max_tokens, timeout):
        gemini_calls["n"] += 1
        return _valid_prd(title="From Gemini Fallback") if gemini_calls["n"] == 1 else {"sections": {}}

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
    assert _prd_title(data) == "From Gemini Fallback"
    assert data["prd"]["provider"] == "gemini_fallback"
    assert gemini_calls["n"] == 2


@pytest.mark.high
async def test_plan_falls_back_to_static_when_both_providers_fail(
    client: AsyncClient, admin_user: User, app, library, monkeypatch
):
    """If Claude AND Gemini both fail, the static plan (first block per
    category) fires so the endpoint never 500s."""
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
    section_types = _prd_home_section_types(data)
    assert section_types[0] == "nav" and section_types[-1] == "footer"
    assert "hero" in section_types and "contact" in section_types
    assert data["status"] == "drafting"
    assistant_turn = next(t for t in data["prompt_history"] if t["role"] == "assistant")
    assert assistant_turn["provider"] == "static_fallback+defaults"


@pytest.mark.high
async def test_plan_invalid_shape_from_claude_triggers_gemini_fallback(
    client: AsyncClient, admin_user: User, app, library, monkeypatch
):
    """Claude returns *something* but no usable sections (unknown ids) →
    the planner skips to Gemini."""
    _patch_settings_keys(monkeypatch, app)
    gemini_calls = {"n": 0}

    async def _fake_claude(**kwargs):
        return {"title": "Half-baked", "sections": [{"variant_id": "nope_nope"}]}

    async def _fake_gemini(**kwargs):
        gemini_calls["n"] += 1
        return _valid_prd(title="Gemini Saves The Day") if gemini_calls["n"] == 1 else {"sections": {}}

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
    assert _prd_title(data) == "Gemini Saves The Day"
    # Gemini planned; the fill call still goes Claude-first (it answered, just emptily)
    assert gemini_calls["n"] == 1
    assert data["prd"]["provider"] == "gemini_fallback" and data["prd"]["fill_provider"] == "claude"


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
    """POST /api/pages/templates/generate-library is wired to the router.

    Enumerates via the OpenAPI spec, not a flat ``app.routes`` walk: Starlette's
    lazy include (``_IncludedRouter``) no longer flattens ``include_router()``
    sub-routers into ``app.routes``, so a top-level walk misses every included
    path even though it is registered and served. See the full explanation in
    ``tests/integration/test_api_route_registration.py::registered_routes``.
    """
    target = "/api/pages/templates/generate-library"
    methods = {m.upper() for m in app.openapi().get("paths", {}).get(target, {})}
    assert methods, f"{target} not registered in the OpenAPI spec"
    assert "POST" in methods
