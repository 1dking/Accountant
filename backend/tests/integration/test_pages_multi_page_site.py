"""S5.1 — AI generation expands nav links into sibling pages inside a Website.

Nate's request (2026-09-07): when the AI generates a site with a nav bar,
generate the pages the nav points to as well. We test:
  1. planner.normalize_plan accepts the new pages[] shape and back-fills legacy sections[]
  2. expand_nav_stubs adds stub pages for every non-anchor href in the home nav
  3. rewrite_nav_hrefs turns "/about" into "/api/pages/public/site/{slug}/about"
  4. generate_page_task creates a Website + one Page per plan entry, home marked
"""
import json
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import User
from app.pages import conversational, planner
from app.pages.models import Page, PageGenerationSession, SectionVariant, Website
from app.pages.seeds.dynamic_blocks import DYNAMIC_BLOCKS
from app.pages.variant_seeds import CTA_VARIANTS, FEATURES_VARIANTS, FOOTER_VARIANTS, HERO_VARIANTS, NAV_VARIANTS, TESTIMONIALS_VARIANTS, FAQ_VARIANTS, TEAM_VARIANTS
from app.pages.variants import _seed_values
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def library(db):
    seeds = [
        *NAV_VARIANTS[:1], *HERO_VARIANTS[:1], *FEATURES_VARIANTS[:1], *TESTIMONIALS_VARIANTS[:1],
        *CTA_VARIANTS[:1], *FAQ_VARIANTS[:1], *TEAM_VARIANTS[:1], *FOOTER_VARIANTS[:1],
        *[v for v in DYNAMIC_BLOCKS if v["variant_id"] in ("contact_lead_form", "faqs_from_data")],
    ]
    for v in seeds:
        db.add(SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v)))
    await db.commit()


# ---------------------------------------------------- normalisation unit ---

def test_normalize_plan_accepts_pages_shape_and_wraps_legacy(library):
    from app.pages.planner import build_catalogue, normalize_plan
    import asyncio
    catalogue = asyncio.get_event_loop().run_until_complete(build_catalogue(_open_db()))
    profile = {}
    # new shape
    p = normalize_plan({"site_title": "Acme", "pages": [
        {"path": "home", "role": "home", "title": "Home", "sections": [{"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": HERO_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
        {"path": "about", "role": "about", "title": "About", "sections": [{"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": TEAM_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
    ]}, catalogue, profile)
    assert p is not None and len(p["pages"]) == 2
    assert p["pages"][0]["is_home"] is True and p["pages"][0]["path"] == "home"
    assert p["pages"][1]["path"] == "about" and p["pages"][1]["is_home"] is False
    # nav + footer share the variant across both pages (allow_repeats)
    assert p["pages"][0]["sections"][0]["variant_id"] == NAV_VARIANTS[0]["variant_id"]
    assert p["pages"][1]["sections"][0]["variant_id"] == NAV_VARIANTS[0]["variant_id"]
    # legacy shape wraps into a single home
    legacy = normalize_plan({"title": "Solo", "sections": [{"variant_id": HERO_VARIANTS[0]["variant_id"]}]}, catalogue, profile)
    assert legacy is not None and len(legacy["pages"]) == 1 and legacy["pages"][0]["is_home"]


def test_apply_nav_from_pages_populates_menu_from_plan(library):
    """Nav is a consequence of the site structure — apply_nav_from_pages
    fills NAV_LINK_n_TEXT/HREF from `plan.pages` on every page's nav so
    the menu can't disagree with the generated pages."""
    from app.pages.planner import apply_nav_from_pages, build_catalogue, normalize_plan
    import asyncio
    catalogue = asyncio.get_event_loop().run_until_complete(build_catalogue(_open_db()))
    plan = normalize_plan({"site_title": "Acme", "pages": [
        {"path": "home",  "title": "Home",  "nav_label": "Home", "sections": [
            {"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": HERO_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
        {"path": "about", "title": "About Us", "nav_label": "About", "sections": [
            {"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": TEAM_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
        {"path": "contact", "title": "Contact", "nav_label": "Contact", "sections": [
            {"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
    ]}, catalogue, {})
    apply_nav_from_pages(plan)
    home_nav = plan["pages"][0]["sections"][0]["fields"]
    assert home_nav["BRAND_NAME"] == "Acme"
    assert home_nav["NAV_LINK_1_TEXT"] == "About" and home_nav["NAV_LINK_1_HREF"] == "about"
    assert home_nav["NAV_LINK_2_TEXT"] == "Contact" and home_nav["NAV_LINK_2_HREF"] == "contact"
    # About page's nav points home + contact (never itself)
    about_nav = plan["pages"][1]["sections"][0]["fields"]
    assert about_nav["NAV_LINK_1_HREF"] == "home" and about_nav["NAV_LINK_2_HREF"] == "contact"


def test_rewrite_nav_hrefs_uses_absolute_site_urls(library):
    from app.pages.planner import build_catalogue, normalize_plan, rewrite_nav_hrefs
    import asyncio
    catalogue = asyncio.get_event_loop().run_until_complete(build_catalogue(_open_db()))
    plan = normalize_plan({"pages": [
        {"path": "home",  "sections": [{"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": HERO_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
        {"path": "about", "sections": [{"variant_id": NAV_VARIANTS[0]["variant_id"]}, {"variant_id": TEAM_VARIANTS[0]["variant_id"]}, {"variant_id": FOOTER_VARIANTS[0]["variant_id"]}]},
    ]}, catalogue, {})
    for p in plan["pages"]:
        p["sections"][0]["fields"] = {
            "NAV_LINK_1_TEXT": "Home",  "NAV_LINK_1_HREF": "/",
            "NAV_LINK_2_TEXT": "About", "NAV_LINK_2_HREF": "about",
            "NAV_LINK_3_TEXT": "Nope",  "NAV_LINK_3_HREF": "missing",
            "NAV_LINK_4_TEXT": "Book",  "NAV_LINK_4_HREF": "https://book.example",
        }
    rewrite_nav_hrefs(plan, "acme-site")
    fields = plan["pages"][0]["sections"][0]["fields"]
    assert fields["NAV_LINK_1_HREF"] == "/api/pages/public/site/acme-site"
    assert fields["NAV_LINK_2_HREF"] == "/api/pages/public/site/acme-site/about"
    assert fields["NAV_LINK_3_HREF"] == "missing"                 # not in plan → left alone
    assert fields["NAV_LINK_4_HREF"] == "https://book.example"    # external untouched


# --------------------------------------------- end-to-end (mocked Sonnet) ---

def _fake_provider(*responses):
    calls = {"n": 0}
    queue = list(responses)

    async def call(**_kwargs):
        calls["n"] += 1
        if not queue:
            return {}
        return queue.pop(0)

    return call, calls


@pytest.mark.high
async def test_generate_task_creates_website_and_sibling_pages(client: AsyncClient, admin_user: User, db, app, session_factory, library, monkeypatch):
    """The planner returns three pages (home + about + services). Every
    page's nav is derived from `plan.pages`, so the menu links to every
    sibling with no fill-time expansion. Result: three Page rows under
    one Website, home marked, nav hrefs point at absolute site URLs."""
    plan = {
        "site_title": "Ottawa Bookkeeping Co.",
        "audience": "Sole proprietors in Ottawa",
        "goals": ["Book a call", "Look credible"],
        "pages": [
            {"path": "home", "role": "home", "title": "Home", "nav_label": "Home",
             "sections": [
                {"variant_id": NAV_VARIANTS[0]["variant_id"], "brief": "Nav"},
                {"variant_id": HERO_VARIANTS[0]["variant_id"], "brief": "Hero pitch"},
                {"variant_id": FEATURES_VARIANTS[0]["variant_id"], "brief": "3 benefits"},
                {"variant_id": FOOTER_VARIANTS[0]["variant_id"], "brief": "Footer"},
             ]},
            {"path": "about", "role": "about", "title": "About Us", "nav_label": "About",
             "sections": [
                {"variant_id": NAV_VARIANTS[0]["variant_id"]},
                {"variant_id": HERO_VARIANTS[0]["variant_id"]},
                {"variant_id": TEAM_VARIANTS[0]["variant_id"]},
                {"variant_id": FOOTER_VARIANTS[0]["variant_id"]},
             ]},
            {"path": "services", "role": "services", "title": "Services", "nav_label": "Services",
             "sections": [
                {"variant_id": NAV_VARIANTS[0]["variant_id"]},
                {"variant_id": HERO_VARIANTS[0]["variant_id"]},
                {"variant_id": FEATURES_VARIANTS[0]["variant_id"]},
                {"variant_id": FOOTER_VARIANTS[0]["variant_id"]},
             ]},
        ],
    }
    fill = {"sections": {
        "1": {"HEADLINE": "Books done right, every month"},
    }}

    fake, calls = _fake_provider(plan, fill)
    monkeypatch.setattr(conversational, "_claude_call_json", fake)
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key", raising=False)

    r = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    sid = r.json()["data"]["id"]
    r = await client.post(f"/api/pages/ai/sessions/{sid}/prompt", headers=auth_header(admin_user),
                          json={"prompt": "Ottawa bookkeeping site", "locale": "en"})
    assert r.status_code == 200, r.text
    prd = r.json()["data"]["prd"]
    assert [p["path"] for p in prd["pages"]] == ["home", "about", "services"]
    # Nav is derived from the plan, filled BEFORE fill_fields runs.
    home_nav = prd["pages"][0]["sections"][0]["fields"]
    assert home_nav["NAV_LINK_1_TEXT"] == "About" and home_nav["NAV_LINK_1_HREF"] == "about"
    assert home_nav["NAV_LINK_2_TEXT"] == "Services" and home_nav["NAV_LINK_2_HREF"] == "services"
    assert home_nav["BRAND_NAME"] == "Ottawa Bookkeeping Co."
    # calls: plan (1) + fill (2) = 2
    assert calls["n"] == 2

    r = await client.post(f"/api/pages/ai/sessions/{sid}/approve", headers=auth_header(admin_user))
    assert r.status_code == 200
    from app.pages.conversational import generate_page_task
    await generate_page_task(uuid.UUID(sid), admin_user.id, session_factory)

    session = (await db.execute(select(PageGenerationSession).where(PageGenerationSession.id == uuid.UUID(sid)))).scalar_one()
    await db.refresh(session)
    assert session.status == "complete", session.error_message
    home = (await db.execute(select(Page).where(Page.id == session.page_id))).scalar_one()
    assert home.is_homepage is True and home.website_id is not None

    website = (await db.execute(select(Website).where(Website.id == home.website_id))).scalar_one()
    all_pages = (await db.execute(select(Page).where(Page.website_id == website.id).order_by(Page.page_order))).scalars().all()
    slugs = [p.slug for p in all_pages]
    assert slugs == ["home", "about", "services"]
    assert [p.is_homepage for p in all_pages] == [True, False, False]
    home_html = home.html_content or ""
    # Nav hrefs on the home page point at absolute site URLs.
    assert f"/api/pages/public/site/{website.slug}/about" in home_html
    assert f"/api/pages/public/site/{website.slug}/services" in home_html
    # About page carries a nav that links back home + to services.
    about = next(p for p in all_pages if p.slug == "about")
    about_html = about.html_content or ""
    assert f"/api/pages/public/site/{website.slug}" in about_html
    assert f"/api/pages/public/site/{website.slug}/services" in about_html


@pytest.mark.high
async def test_generate_task_single_page_plan_skips_website(client: AsyncClient, admin_user: User, db, app, session_factory, library, monkeypatch):
    """A one-page plan (no nav destinations) still creates a standalone
    Page without a Website — nothing to link between."""
    plan = {"pages": [{
        "path": "home", "role": "home", "title": "Only", "sections": [
            {"variant_id": HERO_VARIANTS[0]["variant_id"]},
            {"variant_id": FOOTER_VARIANTS[0]["variant_id"]},
        ],
    }]}
    fill = {"sections": {"0": {"HEADLINE": "Just this page"}}}
    fake, _ = _fake_provider(plan, fill)
    monkeypatch.setattr(conversational, "_claude_call_json", fake)
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key", raising=False)

    r = await client.post("/api/pages/ai/sessions", headers=auth_header(admin_user))
    sid = r.json()["data"]["id"]
    await client.post(f"/api/pages/ai/sessions/{sid}/prompt", headers=auth_header(admin_user),
                      json={"prompt": "Just a landing", "locale": "en"})
    await client.post(f"/api/pages/ai/sessions/{sid}/approve", headers=auth_header(admin_user))
    from app.pages.conversational import generate_page_task
    await generate_page_task(uuid.UUID(sid), admin_user.id, session_factory)
    session = (await db.execute(select(PageGenerationSession).where(PageGenerationSession.id == uuid.UUID(sid)))).scalar_one()
    await db.refresh(session)
    page = (await db.execute(select(Page).where(Page.id == session.page_id))).scalar_one()
    assert page.website_id is None                             # single-page → no Website
    assert page.is_homepage is True
    assert "Just this page" in (page.html_content or "")


# --------------------------------------------------------------- helpers ---

def _open_db():
    """Small helper for the sync-context unit tests above — they need a
    catalogue but not a full page insert, so a fresh session_factory call
    is fine. Uses the same app-state factory the test client uses."""
    import pytest
    # Grab the current session from pytest's fixture cache.
    return _current_session[0]


_current_session: list = []


@pytest.fixture(autouse=True)
def _capture_session(db):
    _current_session.clear()
    _current_session.append(db)
    yield
    _current_session.clear()
