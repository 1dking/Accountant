"""Pages v2 — animation engine (Commit 4).

Tests:
  - variant_to_section() snapshots default_animations into the section
  - compile_page injects GSAP CDN + init script only when sections have animations
  - compile_page omits both when no animations present
  - compile_page falls back to variant_animations dict for legacy sections
  - init script honors prefers-reduced-motion with explicit final state
  - fetch_variant_animations_for_page returns the expected dict
  - hero variants ship with the right animation shapes
"""
import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.compiler import compile_page
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.variant_seeds import HERO_VARIANTS
from app.pages.variants import (
    fetch_variant_animations_for_page, variant_to_section,
)


@pytest_asyncio.fixture
async def seeded_variants(db: AsyncSession) -> int:
    """Seed the 4 hero variants WITH their default_animations."""
    count = 0
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
        count += 1
    await db.commit()
    return count


# ---------------------------------------------------------------------------
# Variant snapshot at insert time
# ---------------------------------------------------------------------------


def test_variant_to_section_snapshots_animations():
    """variant_to_section copies default_animations into section dict.
    Future per-section overrides modify section['animations'] without
    touching the variant template."""
    class _V:
        variant_id = "hero_video"
        category = "hero"
        display_name = "X"
        description = ""
        jsx_template = "<section>{{HEADLINE}}</section>"
        default_props = {"HEADLINE": "Hi"}
        default_animations = {"scroll_reveal": [{"selector": "h1"}]}

    sec = variant_to_section(_V())
    assert sec.get("animations") == {"scroll_reveal": [{"selector": "h1"}]}


def test_variant_to_section_omits_animations_when_variant_has_none():
    """Variants without animations don't get an empty 'animations' key
    — keeps the section dict clean."""
    class _V:
        variant_id = "x"
        category = "hero"
        display_name = "X"
        description = ""
        jsx_template = "<section>x</section>"
        default_props = {}
        default_animations = None

    sec = variant_to_section(_V())
    assert "animations" not in sec


# ---------------------------------------------------------------------------
# Hero variant seed smoke
# ---------------------------------------------------------------------------


def test_hero_video_variant_has_scroll_reveal_for_h1():
    v = next(v for v in HERO_VARIANTS if v["variant_id"] == "hero_video")
    anims = v.get("default_animations")
    assert anims is not None
    selectors = [r["selector"] for r in anims.get("scroll_reveal", [])]
    assert "h1" in selectors


def test_hero_with_stats_variant_has_counter_up_animation():
    v = next(v for v in HERO_VARIANTS if v["variant_id"] == "hero_with_stats")
    anims = v.get("default_animations")
    assert anims is not None
    assert "counter_up" in anims
    assert len(anims["counter_up"]) >= 1


# ---------------------------------------------------------------------------
# compile_page injection
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def animated_page(db: AsyncSession, admin_user: User) -> Page:
    """Page with one section carrying an inline animation snapshot."""
    p = Page(
        id=uuid.uuid4(),
        title="Animated",
        slug=f"anim-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([{
            "id": "hero", "type": "hero", "title": "Hero",
            "jsx_content": "<section><h1>Hi</h1><p>Sub</p></section>",
            "animations": {
                "scroll_reveal": [
                    {"selector": "h1", "from": {"y": 40, "opacity": 0},
                     "to": {"y": 0, "opacity": 1}, "duration": 0.9},
                ],
            },
            "metadata": {"variant_id": "hero_video", "props": {}},
        }]),
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest_asyncio.fixture
async def static_page(db: AsyncSession, admin_user: User) -> Page:
    """Page with one section that has NO animations at all."""
    p = Page(
        id=uuid.uuid4(),
        title="Static",
        slug=f"static-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([{
            "id": "hero", "type": "hero", "title": "Hero",
            "jsx_content": "<section><h1>Static</h1></section>",
            "metadata": {},
        }]),
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def test_compile_page_injects_gsap_and_init_when_section_has_animations(
    animated_page: Page,
):
    """The compiled HTML for a page with animated sections must
    include the GSAP CDN script + the init script + a
    data-section-anim wrapper on the section."""
    html = compile_page(animated_page, company_settings=None)
    assert "gsap.min.js" in html
    assert "ScrollTrigger.min.js" in html
    assert "data-section-anim=" in html
    assert "registerPlugin(ScrollTrigger)" in html


def test_compile_page_omits_animation_assets_when_no_animations(
    static_page: Page,
):
    """Static pages don't pay the GSAP cost. ~25KB saving per page."""
    html = compile_page(static_page, company_settings=None)
    assert "gsap.min.js" not in html
    assert "ScrollTrigger" not in html
    assert "data-section-anim=" not in html


def test_compile_page_uses_variant_animations_fallback_for_legacy_sections(
    static_page: Page,
):
    """Legacy section (no inline 'animations' snapshot) WITH a
    metadata.variant_id pointing to a known variant should pick up
    the variant's animations via the variant_animations fallback dict.

    This is the zero-migration path — existing pages light up on
    next compile without any data change."""
    # Mutate the section to add a variant_id but no inline animations
    secs = json.loads(static_page.sections_json)
    secs[0]["metadata"] = {"variant_id": "hero_video"}
    static_page.sections_json = json.dumps(secs)

    # Now pass the variant_animations dict as the publisher / router
    # would do via fetch_variant_animations_for_page.
    fallback = {"hero_video": {"scroll_reveal": [{"selector": "h1"}]}}
    html = compile_page(
        static_page, company_settings=None,
        variant_animations=fallback,
    )
    assert "gsap.min.js" in html
    assert "data-section-anim=" in html


def test_init_script_explicitly_handles_prefers_reduced_motion(
    animated_page: Page,
):
    """The init script must EXPLICITLY set elements to final visible
    state when prefers-reduced-motion is set — not just early-return.
    Locks in the Commit 4 requirement #1 contract."""
    html = compile_page(animated_page, company_settings=None)
    assert "prefers-reduced-motion: reduce" in html
    # Final-state restoration: opacity 1 + transform none on selected els
    assert "el.style.opacity = '1'" in html
    assert "el.style.transform = 'none'" in html


@pytest.mark.high
async def test_fetch_variant_animations_for_page_returns_map(
    db: AsyncSession, seeded_variants: int, admin_user: User,
):
    """Helper pre-fetches {variant_id → animations} for the variant
    ids referenced by a page's sections. Returns {} when no variant
    ids found."""
    sections_json = json.dumps([
        {"metadata": {"variant_id": "hero_video"}},
        {"metadata": {"variant_id": "hero_two_col_image"}},
        {"metadata": {}},  # no variant_id — ignored
    ])
    m = await fetch_variant_animations_for_page(db, sections_json)
    assert "hero_video" in m
    assert "hero_two_col_image" in m
    # Both are valid animation configs (non-empty dicts)
    assert isinstance(m["hero_video"], dict)
    assert m["hero_video"].get("scroll_reveal")


@pytest.mark.normal
async def test_fetch_variant_animations_handles_empty_sections(
    db: AsyncSession,
):
    """No sections / malformed JSON / missing variant_ids → empty dict.
    Caller can safely pass it on to compile_page."""
    assert await fetch_variant_animations_for_page(db, None) == {}
    assert await fetch_variant_animations_for_page(db, "") == {}
    assert await fetch_variant_animations_for_page(db, "not json") == {}
    assert await fetch_variant_animations_for_page(db, "[]") == {}
    assert await fetch_variant_animations_for_page(
        db, json.dumps([{"metadata": {}}]),
    ) == {}
