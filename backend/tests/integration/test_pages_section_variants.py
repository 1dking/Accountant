"""Pages v2 — section variant library + change-variant + add-section.

Tests the variant infrastructure that backs the SectionEditor picker
modal. Seeds variants directly into the test DB via the same seed
script the app uses on startup (variant_seeds.HERO_VARIANTS) so tests
exercise the real templates.
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.variant_seeds import HERO_VARIANTS
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def seeded_variants(db: AsyncSession) -> int:
    """Seed the 4 hero variants from variant_seeds into the test DB."""
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
            sort_order=v.get("sort_order", 100),
            is_active=True,
        ))
        count += 1
    await db.commit()
    return count


@pytest_asyncio.fixture
async def v2_page(db: AsyncSession, admin_user: User) -> Page:
    """A v2-shape page with one existing hero_video section that has
    metadata.variant_id set, so change-variant can extract tokens
    from its previous template."""
    hero = HERO_VARIANTS[0]  # hero_video
    from app.pages.variants import render_template
    rendered = render_template(hero["jsx_template"], hero["default_props"])
    p = Page(
        id=uuid.uuid4(),
        title="Test V2 Page",
        slug=f"test-v2-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {
                "id": "hero-stable-id",
                "type": "hero",
                "title": "Hero",
                "jsx_content": rendered,
                "metadata": {
                    "variant_id": "hero_video",
                    "props": hero["default_props"],
                },
            }
        ]),
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.high
async def test_list_variants_for_hero_returns_seeded_set(
    client: AsyncClient, admin_user: User, seeded_variants: int
):
    """GET /api/pages/variants?category=hero lists the 4 hero variants
    in sort_order, with the public fields the picker needs."""
    resp = await client.get(
        "/api/pages/variants?category=hero",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == seeded_variants
    # Ordered by sort_order (10, 20, 30, 40)
    variant_ids = [v["variant_id"] for v in data]
    assert variant_ids == [
        "hero_video", "hero_two_col_image", "hero_two_col_form", "hero_with_stats",
    ]
    # Each row has the picker fields
    first = data[0]
    assert "display_name" in first
    assert "description" in first
    assert "default_props" in first
    assert isinstance(first["default_props"], dict)


@pytest.mark.high
async def test_change_variant_replaces_jsx_content_and_preserves_id(
    client: AsyncClient, admin_user: User, v2_page: Page, seeded_variants: int
):
    """POST /sections/{idx}/change-variant swaps the variant. New
    jsx_content reflects the new template. Section id stays stable
    so anchors/bookmarks don't break."""
    resp = await client.post(
        f"/api/pages/{v2_page.id}/sections/0/change-variant",
        json={"category": "hero", "variant_id": "hero_two_col_image"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert sections[0]["id"] == "hero-stable-id"  # preserved
    assert sections[0]["metadata"]["variant_id"] == "hero_two_col_image"
    # Template is now the two-col-image one (grid lg:grid-cols-2)
    assert "lg:grid-cols-2" in sections[0]["jsx_content"]
    # html_content recompiled
    assert "lg:grid-cols-2" in (data["html_content"] or "")


@pytest.mark.high
async def test_change_variant_migrates_matching_token_values(
    client: AsyncClient, admin_user: User, v2_page: Page, seeded_variants: int
):
    """When swapping variants, token values that exist in BOTH
    templates (e.g. HEADLINE, SUBHEADLINE, CTA_PRIMARY_TEXT) carry
    over from the old section's rendered content."""
    # First, customize the old section's HEADLINE so we can detect
    # whether it migrates.
    from app.pages.variant_seeds import HERO_VARIANTS
    from app.pages.variants import render_template
    custom_props = {**HERO_VARIANTS[0]["default_props"], "HEADLINE": "MY CUSTOM HEADLINE"}
    rendered = render_template(HERO_VARIANTS[0]["jsx_template"], custom_props)

    # Update v2_page with the customized rendered content
    sections = json.loads(v2_page.sections_json)
    sections[0]["jsx_content"] = rendered
    sections[0]["metadata"]["props"] = custom_props
    # (we keep variant_id=hero_video so change-variant can find the
    # old template for token extraction)
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession  # type: ignore[unused-import]
    # Persist via the API to avoid juggling db sessions
    patch_resp = await client.patch(
        f"/api/pages/{v2_page.id}/sections/0",
        json={"edited_html": rendered},
        headers=auth_header(admin_user),
    )
    assert patch_resp.status_code == 200

    # Now swap to hero_two_col_image
    resp = await client.post(
        f"/api/pages/{v2_page.id}/sections/0/change-variant",
        json={"category": "hero", "variant_id": "hero_two_col_image"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    meta = resp.json()["meta"]
    # At least HEADLINE should have migrated
    assert "HEADLINE" in meta["migrated_tokens"]
    sections = json.loads(data["sections_json"])
    # Custom headline survived the variant swap
    assert "MY CUSTOM HEADLINE" in sections[0]["jsx_content"]


@pytest.mark.high
async def test_add_section_appends_at_end_by_default(
    client: AsyncClient, admin_user: User, v2_page: Page, seeded_variants: int
):
    """POST /sections appends a new section from a variant at the
    end of sections_json. Returns the new section's index in meta."""
    resp = await client.post(
        f"/api/pages/{v2_page.id}/sections",
        json={"category": "hero", "variant_id": "hero_with_stats"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    meta = resp.json()["meta"]
    sections = json.loads(data["sections_json"])
    assert len(sections) == 2  # was 1
    assert meta["new_section_index"] == 1
    assert sections[1]["metadata"]["variant_id"] == "hero_with_stats"
    # html_content recompiled with both sections
    assert "Trusted by founders" in (data["html_content"] or "")


@pytest.mark.normal
async def test_add_section_inserts_at_position_via_after_idx(
    client: AsyncClient, admin_user: User, v2_page: Page, seeded_variants: int
):
    """?after_idx=0 inserts the new section at index 1 (immediately
    after existing section 0). Original section 0 stays at index 0."""
    resp = await client.post(
        f"/api/pages/{v2_page.id}/sections?after_idx=0",
        json={"category": "hero", "variant_id": "hero_with_stats"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert len(sections) == 2
    assert sections[0]["id"] == "hero-stable-id"  # original
    assert sections[1]["metadata"]["variant_id"] == "hero_with_stats"


@pytest.mark.normal
async def test_change_variant_unknown_returns_404(
    client: AsyncClient, admin_user: User, v2_page: Page
):
    """Unknown category/variant_id returns 404 with the bad pair in
    the message — UI surfaces a useful error."""
    resp = await client.post(
        f"/api/pages/{v2_page.id}/sections/0/change-variant",
        json={"category": "hero", "variant_id": "does_not_exist"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404
    body = resp.json()
    assert "does_not_exist" in body["error"]["message"]
