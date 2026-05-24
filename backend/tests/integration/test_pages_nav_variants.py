"""Pages v2 — nav variant category (Commit 6 Workstream C.1).

Tests:
  - all 3 nav variants are present in seed catalog with valid shape
  - SVG schematics exist for each nav variant
  - new page auto-prepends nav_transparent_on_hero when the variant
    is seeded in the DB (Option B rollout — existing pages unchanged)
  - change-variant swaps between nav variants cleanly
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.variant_seeds import NAV_VARIANTS, all_variants
from app.pages.variant_svg_schematics import SCHEMATICS_BY_VARIANT_ID
from app.pages.schemas import PageCreate
from app.pages import service
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. Seed-shape assertions — pure unit, no DB
# ---------------------------------------------------------------------------


@pytest.mark.normal
def test_three_nav_variants_present():
    """Three flagship navs ship in Commit 6: transparent_on_hero,
    solid_always, centered_logo. Each is the canonical reference
    pattern for that nav style."""
    ids = {v["variant_id"] for v in NAV_VARIANTS}
    assert ids == {
        "nav_transparent_on_hero",
        "nav_solid_always",
        "nav_centered_logo",
    }
    # Each variant carries the same minimal token shape so a swap
    # between them migrates content cleanly.
    for v in NAV_VARIANTS:
        assert v["category"] == "nav"
        assert v["jsx_template"].lstrip().startswith("<nav")
        assert "BRAND_NAME" in v["default_props"]


@pytest.mark.normal
def test_nav_variants_have_svg_schematics():
    """All 3 nav variants must have an SVG schematic registered, or
    the picker card renders blank."""
    for v in NAV_VARIANTS:
        assert v["variant_id"] in SCHEMATICS_BY_VARIANT_ID, (
            f"nav variant {v['variant_id']} missing SVG schematic"
        )
        svg = SCHEMATICS_BY_VARIANT_ID[v["variant_id"]]
        assert svg.startswith("<svg")
        # Schematics use the shared lg-accent gradient defs
        assert "lg-accent" in svg


@pytest.mark.normal
def test_nav_category_in_all_variants():
    """all_variants() exposes nav as the 13th category — picker shows
    a 'Nav' tab in the category grid."""
    cats = {v["category"] for v in all_variants()}
    assert "nav" in cats
    nav_count = sum(1 for v in all_variants() if v["category"] == "nav")
    assert nav_count == 3


# ---------------------------------------------------------------------------
# 2. Auto-prepend on new page creation (Option B)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_nav_variants(db: AsyncSession) -> int:
    """Seed the 3 nav variants into the test DB so create_page can
    find nav_transparent_on_hero for auto-prepend."""
    for v in NAV_VARIANTS:
        db.add(SectionVariant(
            id=v["id"],
            category=v["category"],
            variant_id=v["variant_id"],
            display_name=v["display_name"],
            description=v.get("description"),
            jsx_template=v["jsx_template"],
            default_props=v.get("default_props", {}),
            default_animations=v.get("default_animations"),
            svg_thumbnail=SCHEMATICS_BY_VARIANT_ID.get(v["variant_id"]),
            sort_order=v.get("sort_order", 100),
            is_active=True,
        ))
    await db.commit()
    return len(NAV_VARIANTS)


@pytest.mark.high
async def test_create_page_auto_prepends_default_nav(
    db: AsyncSession, admin_user: User, seeded_nav_variants: int,
):
    """New pages get nav_transparent_on_hero as section[0] when the
    variant is seeded. Lets users start customizing nav immediately
    instead of having to find and add it."""
    data = PageCreate(title="Brand new page", description="d")
    page = await service.create_page(db, data, admin_user)
    assert page.sections_json is not None
    sections = json.loads(page.sections_json)
    assert len(sections) == 1
    assert sections[0]["type"] == "nav"
    assert sections[0]["metadata"]["variant_id"] == "nav_transparent_on_hero"


@pytest.mark.normal
async def test_create_page_works_when_nav_variant_not_seeded(
    db: AsyncSession, admin_user: User,
):
    """Defensive — page creation must NOT fail just because the nav
    variant table is empty (e.g. fresh test DB before seed). Pages
    just come up with no sections; identical to pre-Commit-6 behavior."""
    data = PageCreate(title="Bare page", description="d")
    page = await service.create_page(db, data, admin_user)
    # sections_json may be None or "[]" — either is acceptable
    assert page.sections_json in (None, "[]")
