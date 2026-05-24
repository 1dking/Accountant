"""Pages v2 — element-level style overrides (Commit 6 Workstream A).

Tests:
  - PATCH /sections/{idx} persists style_overrides → sections_json
  - compile_page emits scoped CSS rules per section
  - Google Fonts <link> injected for catalog families (single tag,
    union of all sections)
  - Unsafe CSS values rejected at compile time
  - section-id wrapper added to every section so the scoped CSS hits
  - style_overrides survives variant swap when selectors still match
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.compiler import compile_page
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.variant_seeds import HERO_VARIANTS
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_variants(db: AsyncSession) -> int:
    """Seed all 4 hero variants — change-variant test needs ≥2."""
    for v in HERO_VARIANTS:
        db.add(SectionVariant(
            id=v["id"],
            category=v["category"],
            variant_id=v["variant_id"],
            display_name=v["display_name"],
            description=v.get("description"),
            jsx_template=v["jsx_template"],
            default_props=v.get("default_props", {}),
            default_animations=v.get("default_animations"),
            sort_order=v.get("sort_order", 100),
            is_active=True,
        ))
    await db.commit()
    return len(HERO_VARIANTS)


def _make_page(admin_user: User, sections: list[dict]) -> Page:
    return Page(
        id=uuid.uuid4(),
        title="Style Test Page",
        slug=f"style-test-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps(sections),
        created_by=admin_user.id,
    )


# ---------------------------------------------------------------------------
# 1. Persistence — PATCH writes style_overrides through
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_style_override_persists_to_section(
    client: AsyncClient, admin_user: User, db: AsyncSession,
    seeded_variants: int,
):
    """PATCH /sections/{idx} with style_overrides updates the section
    in sections_json (no global css_content writes — closes the
    bug #10 architectural mismatch)."""
    page = _make_page(admin_user, [
        {
            "id": "hero-1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "metadata": {"variant_id": "hero_video"},
        },
    ])
    db.add(page)
    await db.commit()
    await db.refresh(page)

    resp = await client.patch(
        f"/api/pages/{page.id}/sections/0",
        json={"style_overrides": {
            "h1": {"fontFamily": "Playfair Display", "fontSize": "64px"},
        }},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(page)
    sections = json.loads(page.sections_json)
    assert sections[0]["style_overrides"]["h1"]["fontSize"] == "64px"
    # css_content not touched by the structured path.
    assert not page.css_content or "64px" not in page.css_content


# ---------------------------------------------------------------------------
# 2. Compile — scoped CSS emitted per section
# ---------------------------------------------------------------------------


def test_compile_applies_style_override_as_scoped_css(admin_user: User):
    """compile_page emits #section-{sid} h1 { ... } in a <style> block
    in <head>. Section is wrapped in <div id="section-{sid}">."""
    page = _make_page(admin_user, [
        {
            "id": "hero-1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "style_overrides": {
                "h1": {"fontSize": "72px", "color": "#ffffff"},
            },
        },
    ])
    html = compile_page(page)

    # Scoped rule in head, not a global "h1 { ... }" stomp
    assert "#section-hero-1 h1 {" in html
    assert "font-size: 72px;" in html
    assert "color: #ffffff;" in html
    # Wrapper applied so the selector resolves
    assert '<section id="section-hero-1"' in html
    # Style block is inside <head>, not body
    head_end = html.index("</head>")
    style_start = html.index('<style id="pages-style-overrides">')
    assert style_start < head_end


def test_section_pseudo_selector_targets_wrapper_and_inner_section(
    admin_user: User,
):
    """'section' pseudo-selector compiles to both the wrapper id and
    its direct-child section descendant. Lets a single declaration
    style the visible section background (which lives on the inner
    <section> in all 15 flagship templates)."""
    page = _make_page(admin_user, [
        {
            "id": "h1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "style_overrides": {
                "section": {"backgroundColor": "#0f1320", "paddingTop": "96px"},
            },
        },
    ])
    html = compile_page(page)
    assert "#section-h1, #section-h1 > section {" in html
    assert "background-color: #0f1320;" in html
    assert "padding-top: 96px;" in html


# ---------------------------------------------------------------------------
# 3. Google Fonts — link injected for catalog families
# ---------------------------------------------------------------------------


def test_google_fonts_link_injected_for_used_families(admin_user: User):
    """Catalog families are collected across sections; a single <link>
    in <head> requests them all. Non-catalog families (system fonts,
    brand stacks) are NOT requested from Google."""
    page = _make_page(admin_user, [
        {
            "id": "s1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "style_overrides": {"h1": {"fontFamily": "Playfair Display"}},
        },
        {
            "id": "s2",
            "type": "features",
            "jsx_content": "<section><p>Hi</p></section>",
            "style_overrides": {"p": {"fontFamily": "Inter"}},
        },
        {
            "id": "s3",
            "type": "cta",
            "jsx_content": "<section><h2>Hi</h2></section>",
            "style_overrides": {"h2": {"fontFamily": "system-ui, sans-serif"}},
        },
    ])
    html = compile_page(page)
    # Both catalog families on a single link, alphabetical.
    assert "fonts.googleapis.com/css2?family=Inter:" in html
    assert "family=Playfair+Display:" in html
    # Exactly one Google Fonts stylesheet link.
    assert html.count('href="https://fonts.googleapis.com/css2?') == 1
    # Non-catalog font NOT requested.
    assert "system-ui" not in html.split("</head>")[0].split(
        'href="https://fonts.googleapis.com'
    )[1] if 'fonts.googleapis.com' in html else True


def test_no_google_fonts_link_when_no_overrides(admin_user: User):
    """Pages without any style_overrides don't pay the Google Fonts
    round-trip cost."""
    page = _make_page(admin_user, [
        {
            "id": "s1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
        },
    ])
    html = compile_page(page)
    assert "fonts.googleapis.com" not in html


# ---------------------------------------------------------------------------
# 4. Multiple selectors per section
# ---------------------------------------------------------------------------


def test_multiple_selectors_per_section_compile(admin_user: User):
    """A single section can override h1, h2, p, and section in one
    style_overrides dict — each maps to its own scoped rule."""
    page = _make_page(admin_user, [
        {
            "id": "multi",
            "type": "hero",
            "jsx_content": "<section><h1>A</h1><h2>B</h2><p>C</p></section>",
            "style_overrides": {
                "h1": {"color": "#fff"},
                "h2": {"color": "#aaa"},
                "p": {"lineHeight": "1.7"},
                "section": {"paddingTop": "48px"},
            },
        },
    ])
    html = compile_page(page)
    assert "#section-multi h1 {" in html
    assert "#section-multi h2 {" in html
    assert "#section-multi p {" in html
    assert "#section-multi, #section-multi > section {" in html


# ---------------------------------------------------------------------------
# 5. Defense — unsafe CSS values are rejected
# ---------------------------------------------------------------------------


def test_unsafe_css_value_rejected_at_compile(admin_user: User):
    """Values with rule-block-breaking chars ({};<>) are dropped, not
    emitted into the page. Defense against drawer injecting via the
    style_overrides payload."""
    page = _make_page(admin_user, [
        {
            "id": "evil",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "style_overrides": {
                "h1": {
                    "color": "red; } body { background: hotpink",
                    "fontSize": "32px",  # safe — should still emit
                },
            },
        },
    ])
    html = compile_page(page)
    # The unsafe color declaration must be dropped entirely.
    assert "hotpink" not in html
    # The safe one alongside it still emits.
    assert "font-size: 32px;" in html


# ---------------------------------------------------------------------------
# 6. Variant swap — style_overrides survive when selectors still match
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_style_overrides_survive_variant_swap(
    client: AsyncClient, admin_user: User, db: AsyncSession,
    seeded_variants: int,
):
    """Variant swap rewrites jsx_content but the section's
    style_overrides dict is preserved — selectors that match elements
    in the new variant continue to apply."""
    page = _make_page(admin_user, [
        {
            "id": "hero-1",
            "type": "hero",
            "jsx_content": "<section><h1>Hi</h1></section>",
            "metadata": {"variant_id": "hero_video"},
            "style_overrides": {"h1": {"color": "#facc15"}},
        },
    ])
    db.add(page)
    await db.commit()
    await db.refresh(page)

    resp = await client.post(
        f"/api/pages/{page.id}/sections/0/change-variant",
        json={"category": "hero", "variant_id": "hero_two_col_image"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(page)
    sections = json.loads(page.sections_json)
    # style_overrides preserved across the swap.
    assert sections[0]["style_overrides"]["h1"]["color"] == "#facc15"
    # The new variant's h1 picks up the color via the scoped rule.
    assert "#facc15" in page.html_content
