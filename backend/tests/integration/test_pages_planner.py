"""S4 — copy-only AI site build: plan blocks from the library, fill fields, materialise via templates."""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages import conversational, planner
from app.pages.models import Page, PageGenerationSession, SectionVariant
from app.pages.seeds.dynamic_blocks import DYNAMIC_BLOCKS
from app.pages.variant_seeds import HERO_VARIANTS, NAV_VARIANTS, FOOTER_VARIANTS
from app.pages.variants import _seed_values
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def library(db: AsyncSession) -> list[SectionVariant]:
    seeds = [*NAV_VARIANTS[:1], *HERO_VARIANTS[:2], *FOOTER_VARIANTS[:1],
             *[v for v in DYNAMIC_BLOCKS if v["variant_id"] in ("contact_lead_form", "booking_inline_picker", "stats_count_up", "faq_searchable")]]
    rows = []
    for v in seeds:
        row = SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v))
        db.add(row)
        rows.append(row)
    await db.commit()
    return rows


def _fake_claude(responses: list[dict], captured: list[dict]):
    async def call(settings, model, system_prompt, user_msg, max_tokens, timeout):
        captured.append({"model": model, "system": system_prompt, "user": user_msg})
        return responses.pop(0)
    return call


@pytest.mark.high
async def test_plan_fill_generate_uses_only_library_templates(client: AsyncClient, app, session_factory, admin_user: User, db: AsyncSession, library, monkeypatch):
    plan = {
        "site_title": "Ottawa Bookkeeping Co.",
        "audience": "Sole proprietors in Ottawa who dread tax season",
        "goals": ["Book a free call", "Show credibility"],
        "pages": [{
            "path": "home", "role": "home", "title": "Ottawa Bookkeeping Co.", "nav_label": "Home",
            "sections": [
                {"variant_id": NAV_VARIANTS[0]["variant_id"], "brief": "Simple nav"},
                {"variant_id": HERO_VARIANTS[0]["variant_id"], "brief": "Bold promise about stress-free books"},
                {"variant_id": "stats_count_up", "brief": "Trust numbers"},
                {"variant_id": "booking_inline_picker", "brief": "Book a call"},        # no calendar → dropped
                {"variant_id": "totally_made_up_block", "category": "faq", "brief": "FAQ"},  # unknown → first faq block
                {"variant_id": "contact_lead_form", "brief": "Lead form"},
                {"variant_id": "contact_lead_form", "brief": "duplicate"},                # deduped
                {"variant_id": FOOTER_VARIANTS[0]["variant_id"], "brief": "Footer"},
            ],
        }],
    }
    fill = {"sections": {
        "1": {"HEADLINE": "Books done right, <b>every month</b>", "SUBHEADLINE": "We keep your CRA filings on time so you can run the shop.",
              "CTA_PRIMARY_TEXT": "Book a free call", "IMAGE_URL": "https://evil/x.jpg", "MADE_UP": "no"},
        "2": {"HEADLINE": "Numbers that matter", "STATS": [{"VALUE": 120, "SUFFIX": "+", "LABEL": "Ottawa clients"}, {"VALUE": 9, "SUFFIX": "yrs", "LABEL": "In business"}]},
        "4": {"HEADLINE": "Tell us about your books", "SUBMIT_TEXT": "Send"},
    }}
    captured: list[dict] = []
    monkeypatch.setattr(conversational, "_claude_call_json", _fake_claude([plan, fill], captured))
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key", raising=False)
    assert planner.PLAN_MODEL.startswith("claude-sonnet")                          # Sonnet-first (owner rule)

    r = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    sid = r.json()["data"]["id"]
    r = await client.post(f"/api/pages/ai/sessions/{sid}/prompt", headers=auth_header(admin_user),
                          json={"prompt": "A landing page for my Ottawa bookkeeping business", "locale": "en"})
    assert r.status_code == 200, r.text
    prd = r.json()["data"]["prd"]
    # single-page plan wraps its sections under one home page
    ids = [s["variant_id"] for s in prd["pages"][0]["sections"]]
    assert ids == [NAV_VARIANTS[0]["variant_id"], HERO_VARIANTS[0]["variant_id"], "stats_count_up", "faq_searchable",
                   "contact_lead_form", FOOTER_VARIANTS[0]["variant_id"]]
    assert prd["provider"] == "claude" and prd["fill_provider"] == "claude"
    # planner prompt carried the catalogue and the profile, never markup instructions
    assert "Block catalogue" in captured[0]["user"] and "never write HTML" in captured[0]["system"]
    assert "Blocks to write" in captured[1]["user"] and "never write HTML" in captured[1]["system"]
    hero = prd["pages"][0]["sections"][1]
    assert hero["fields"]["HEADLINE"] == "Books done right, every month"       # tags stripped
    assert "IMAGE_URL" not in hero["fields"] and "MADE_UP" not in hero["fields"]  # locked / unknown dropped
    assert hero["thumbnail_url"] is None or isinstance(hero["thumbnail_url"], str)
    stats = prd["pages"][0]["sections"][2]
    assert stats["fields"]["STATS"][0] == {"VALUE": 120, "SUFFIX": "+", "LABEL": "Ottawa clients"}

    r = await client.post(f"/api/pages/ai/sessions/{sid}/approve", headers=auth_header(admin_user))
    assert r.status_code == 200
    from app.pages.conversational import generate_page_task
    await generate_page_task(uuid.UUID(sid), admin_user.id, session_factory)

    session = (await db.execute(select(PageGenerationSession).where(PageGenerationSession.id == uuid.UUID(sid)))).scalar_one()
    await db.refresh(session)
    assert session.status == "complete", session.error_message
    page = (await db.execute(select(Page).where(Page.id == session.page_id))).scalar_one()
    sections = json.loads(page.sections_json)
    assert [s["metadata"]["variant_id"] for s in sections] == ids
    hero_sec = sections[1]
    assert "Books done right, every month" in hero_sec["jsx_content"]
    assert hero_sec["metadata"]["schema_version"] == 2 and hero_sec["metadata"]["provider"] == "claude"
    assert "https://evil/x.jpg" not in json.dumps(hero_sec)                         # locked media never overwritten
    assert 'data-lead-form' in sections[4]["jsx_content"]                            # real template, not AI markup
    assert 'data-count-to="120"' in sections[2]["jsx_content"]
    assert "Books done right, every month" in (page.html_content or "")
    assert len(captured) == 2                                                        # plan + fill only; no per-section JSX calls


@pytest.mark.high
async def test_static_plan_when_no_provider(client: AsyncClient, app, admin_user: User, db: AsyncSession, library, monkeypatch):
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "", raising=False)
    monkeypatch.setattr(app.state.settings, "gemini_api_key", "", raising=False)
    r = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    sid = r.json()["data"]["id"]
    r = await client.post(f"/api/pages/ai/sessions/{sid}/prompt", headers=auth_header(admin_user),
                          json={"prompt": "Plumber in Gatineau", "locale": "fr-CA"})
    assert r.status_code == 200, r.text
    prd = r.json()["data"]["prd"]
    assert prd["provider"] == "static_fallback" and prd["fill_provider"] == "defaults"
    cats = [s["type"] for s in prd["pages"][0]["sections"]]
    assert cats[0] == "nav" and cats[-1] == "footer" and "hero" in cats and "contact" in cats
    assert "booking" not in cats                                                     # no calendar on this account
    lead = next(s for s in prd["pages"][0]["sections"] if s["variant_id"] == "contact_lead_form")
    assert lead["fields"]["HEADLINE"] == "Parlez-nous de votre projet"                # fr-CA defaults
