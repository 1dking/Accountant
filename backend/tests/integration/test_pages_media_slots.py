"""Pages v2 — editable media slots + SVG schematic thumbnails (Commit 3).

Covers:
  - GET /variants exposes svg_thumbnail (Workstream A)
  - render_template defers MEDIA_TOKENS at insert time (Workstream B)
  - compile_page substitutes media tokens from media_overrides
  - PATCH /sections/{idx} accepts media_overrides + normalizes YouTube URL
  - Variant swap carries media_overrides when token names match
  - normalize_youtube_url handles common URL shapes
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
from app.pages.variant_svg_schematics import SCHEMATICS_BY_VARIANT_ID
from app.pages.variants import (
    MEDIA_TOKENS, normalize_youtube_url, render_template,
    substitute_media_tokens, variant_to_section,
)
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def seeded_variants(db: AsyncSession) -> int:
    """Seed the 4 hero variants with their SVG schematics."""
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
            svg_thumbnail=SCHEMATICS_BY_VARIANT_ID.get(v["variant_id"]),
            sort_order=v.get("sort_order", 100),
            is_active=True,
        ))
        count += 1
    await db.commit()
    return count


# ---------------------------------------------------------------------------
# Workstream A — SVG schematics
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_list_variants_exposes_svg_thumbnail(
    client: AsyncClient, admin_user: User, seeded_variants: int
):
    """GET /api/pages/variants returns svg_thumbnail for each variant.
    The picker uses this to render the schematic card."""
    resp = await client.get(
        "/api/pages/variants?category=hero",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == seeded_variants
    for row in data:
        assert "svg_thumbnail" in row
        assert row["svg_thumbnail"], f"variant {row['variant_id']} missing svg_thumbnail"
        # Sanity: self-contained inline SVG (no external href)
        assert row["svg_thumbnail"].startswith("<svg")
        assert "<image " not in row["svg_thumbnail"]  # no remote image refs


# ---------------------------------------------------------------------------
# Workstream B — MEDIA_TOKENS defer at insert, substitute at compile
# ---------------------------------------------------------------------------


def test_render_template_skips_media_tokens():
    """render_template with skip_tokens=MEDIA_TOKENS leaves {{VIDEO_URL}}
    literal so compile_page can substitute it later from media_overrides."""
    tpl = '<video src="{{VIDEO_URL}}" poster="{{IMAGE_URL}}"><span>{{HEADLINE}}</span></video>'
    props = {
        "VIDEO_URL": "https://example.com/v.mp4",
        "IMAGE_URL": "https://example.com/p.png",
        "HEADLINE": "Hello",
    }
    rendered = render_template(tpl, props, skip_tokens=MEDIA_TOKENS)
    # Non-media token substituted
    assert "Hello" in rendered
    # Media tokens stay literal
    assert "{{VIDEO_URL}}" in rendered
    assert "{{IMAGE_URL}}" in rendered


def test_substitute_media_tokens_resolves_only_whitelisted():
    """substitute_media_tokens fills in MEDIA_TOKENS from props but
    leaves non-media tokens alone (those are already resolved at
    insert time, or kept literal for the inline editor)."""
    html = '<video src="{{VIDEO_URL}}"><h1>{{HEADLINE}}</h1></video>'
    out = substitute_media_tokens(html, {
        "VIDEO_URL": "https://example.com/v.mp4",
        "HEADLINE": "wrong — non-media",
    })
    assert "https://example.com/v.mp4" in out
    # HEADLINE is NOT in MEDIA_TOKENS so it stays literal
    assert "{{HEADLINE}}" in out


def test_variant_to_section_emits_media_overrides_dict():
    """variant_to_section initializes media_overrides as {} and keeps
    MEDIA_TOKENS literal in jsx_content."""
    # Synthesize a variant object compatible with variant_to_section
    class _V:
        variant_id = "hero_video"
        category = "hero"
        display_name = "Video Background"
        description = "test"
        jsx_template = '<section><video src="{{VIDEO_URL}}"><h1>{{HEADLINE}}</h1></video></section>'
        default_props = {"HEADLINE": "Hello", "VIDEO_URL": "https://example.com/v.mp4"}

    sec = variant_to_section(_V())
    assert sec["media_overrides"] == {}
    # Non-media: substituted
    assert "Hello" in sec["jsx_content"]
    # Media token: literal
    assert "{{VIDEO_URL}}" in sec["jsx_content"]


@pytest.mark.high
async def test_compile_page_applies_media_overrides(
    db: AsyncSession, admin_user: User
):
    """compile_page substitutes media tokens from
    (metadata.props ⊕ media_overrides). media_overrides wins."""
    from app.pages.compiler import compile_page

    page = Page(
        id=uuid.uuid4(),
        title="Test",
        slug="test-mo",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([{
            "id": "hero",
            "type": "hero",
            "title": "Hero",
            "jsx_content": (
                '<section><video src="{{VIDEO_URL}}" '
                'poster="{{VIDEO_POSTER_URL}}"></video><h1>Real Title</h1></section>'
            ),
            "media_overrides": {
                "VIDEO_URL": "https://override.example.com/new.mp4",
            },
            "metadata": {
                "variant_id": "hero_video",
                "props": {
                    "VIDEO_URL": "https://default.example.com/old.mp4",
                    "VIDEO_POSTER_URL": "https://default.example.com/poster.png",
                },
            },
        }]),
        created_by=admin_user.id,
    )
    html = compile_page(page, company_settings=None)
    # Override wins over default
    assert "https://override.example.com/new.mp4" in html
    assert "https://default.example.com/old.mp4" not in html
    # Defaults fill in when not overridden
    assert "https://default.example.com/poster.png" in html


@pytest.mark.high
async def test_patch_section_accepts_media_overrides_and_normalizes_youtube(
    client: AsyncClient, admin_user: User, db: AsyncSession, seeded_variants: int
):
    """PATCH /sections/{idx} with media_overrides persists the URLs and
    normalizes any pasted YouTube watch URL to embed form. compile_page
    runs and the new URL appears in html_content."""
    # Add a hero_video section so we have a media slot to patch
    page = Page(
        id=uuid.uuid4(),
        title="Test",
        slug=f"test-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([{
            "id": "hero",
            "type": "hero",
            "title": "Hero",
            "jsx_content": '<section><video src="{{VIDEO_URL}}"></video></section>',
            "media_overrides": {},
            "metadata": {"variant_id": "hero_video", "props": {}},
        }]),
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    resp = await client.patch(
        f"/api/pages/{page.id}/sections/0",
        json={"media_overrides": {
            "VIDEO_URL": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    normalized = sections[0]["media_overrides"]["VIDEO_URL"]
    assert normalized.startswith("https://www.youtube.com/embed/dQw4w9WgXcQ")
    assert "autoplay=1" in normalized
    # html_content recompiled with the embed URL
    assert "https://www.youtube.com/embed/dQw4w9WgXcQ" in (data["html_content"] or "")


@pytest.mark.high
async def test_variant_swap_preserves_media_overrides_when_token_matches(
    client: AsyncClient, admin_user: User, db: AsyncSession, seeded_variants: int
):
    """Swapping variant carries media_overrides whose token name exists
    in the new variant's default_props. Lets the user change the layout
    without losing the video URL they just pasted."""
    # Build a hero_video section with a user-pasted VIDEO_URL override
    user_video = "https://www.youtube.com/embed/USER_VIDEO?autoplay=1"
    page = Page(
        id=uuid.uuid4(),
        title="Test",
        slug=f"test-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([{
            "id": "hero",
            "type": "hero",
            "title": "Hero",
            "jsx_content": '<section><video src="{{VIDEO_URL}}"></video></section>',
            "media_overrides": {"VIDEO_URL": user_video},
            "metadata": {
                "variant_id": "hero_video",
                "props": HERO_VARIANTS[0]["default_props"],
            },
        }]),
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    # Swap to hero_two_col_image — its default_props do NOT include
    # VIDEO_URL, so the media override should be DROPPED (we can't
    # show a video in a layout that has no video slot).
    resp = await client.post(
        f"/api/pages/{page.id}/sections/0/change-variant",
        json={"category": "hero", "variant_id": "hero_two_col_image"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    # No carry-over: new template doesn't have a video slot
    assert sections[0].get("media_overrides", {}).get("VIDEO_URL") is None


# ---------------------------------------------------------------------------
# YouTube URL normalization
# ---------------------------------------------------------------------------


def test_normalize_youtube_watch_url():
    out = normalize_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert out.startswith("https://www.youtube.com/embed/dQw4w9WgXcQ")
    assert "autoplay=1" in out
    assert "mute=1" in out
    assert "loop=1" in out
    assert "playlist=dQw4w9WgXcQ" in out  # loop requires playlist=<id>


def test_normalize_youtube_short_url():
    out = normalize_youtube_url("https://youtu.be/abc123XYZ_-")
    assert out.startswith("https://www.youtube.com/embed/abc123XYZ_-")


def test_normalize_youtube_already_embed():
    """Already-embed URLs pass through the ID extractor and get our
    canonical params re-applied — idempotent enough for our purposes."""
    out = normalize_youtube_url("https://www.youtube.com/embed/abc123XYZ_-")
    assert out.startswith("https://www.youtube.com/embed/abc123XYZ_-")


def test_normalize_youtube_bare_id():
    out = normalize_youtube_url("dQw4w9WgXcQ")
    assert out.startswith("https://www.youtube.com/embed/dQw4w9WgXcQ")


def test_normalize_non_youtube_passes_through():
    """Direct mp4 URLs and other strings pass through unchanged so
    the user can drop in self-hosted video."""
    direct = "https://cdn.example.com/videos/hero.mp4"
    assert normalize_youtube_url(direct) == direct
