"""Block model v2 — PATCH /sections/{i} with `props`, /variants v2 shape,
and compile output for motion presets."""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.variants import variant_to_section
from tests.conftest import auth_header

V2_SEED = {
    "id": "var_test_v2_hero",
    "category": "hero",
    "variant_id": "test_v2_hero",
    "display_name": "Test v2 hero",
    "description": "v2 block for tests",
    "jsx_template": (
        '<section className="hero"><h1>{{HEADLINE}}</h1><p>{{SUBHEADLINE}}</p>'
        '<ul>{{#BULLETS}}<li data-i="{{@INDEX}}">{{VALUE}}</li>{{/BULLETS}}</ul>'
        '<a href="{{CTA_HREF}}">{{CTA_TEXT}}</a><img src="{{IMAGE_URL}}"/></section>'
    ),
    "default_props": {
        "HEADLINE": "Default headline",
        "SUBHEADLINE": "Default sub",
        "BULLETS": ["One", "Two"],
        "CTA_HREF": "#",
        "CTA_TEXT": "Go",
        "IMAGE_URL": "https://img.example.com/a.webp",
    },
    "fields_schema": [
        {"key": "HEADLINE", "type": "text", "required": True, "max_len": 40},
        {"key": "SUBHEADLINE", "type": "textarea"},
        {"key": "BULLETS", "type": "list", "max_items": 3, "item_fields": [{"key": "VALUE", "type": "text"}]},
        {"key": "CTA_HREF", "type": "url"},
        {"key": "CTA_TEXT", "type": "text"},
        {"key": "IMAGE_URL", "type": "image"},
    ],
    "locale_props": {"fr-CA": {"HEADLINE": "Titre par défaut", "CTA_TEXT": "Allons-y"}},
    "schema_version": 2,
    "motion_preset": "css_reveal_up",
    "capabilities": ["motion_css"],
}


@pytest_asyncio.fixture
async def v2_variant(db: AsyncSession) -> SectionVariant:
    from app.pages.variants import _seed_values
    row = SectionVariant(
        id=V2_SEED["id"], category=V2_SEED["category"], variant_id=V2_SEED["variant_id"],
        is_active=True, **_seed_values(V2_SEED),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest_asyncio.fixture
async def v2_page(db: AsyncSession, admin_user: User, v2_variant: SectionVariant) -> Page:
    section = variant_to_section(v2_variant)
    p = Page(
        id=uuid.uuid4(), title="Block fields page", slug=f"bf-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT, sections_json=json.dumps([section]), created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def _first_section(resp_json: dict) -> dict:
    return json.loads(resp_json["data"]["sections_json"])[0]


@pytest.mark.high
async def test_variants_endpoint_exposes_v2_shape(client: AsyncClient, admin_user: User, v2_variant):
    resp = await client.get("/api/pages/variants?category=hero", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    row = next(v for v in body["data"] if v["variant_id"] == "test_v2_hero")
    assert row["schema_version"] == 2
    assert [f["key"] for f in row["fields_schema"]][:2] == ["HEADLINE", "SUBHEADLINE"]
    assert row["motion_preset"] == "css_reveal_up"
    assert row["capabilities"] == ["motion_css"]
    assert row["locales"] == ["fr-CA"]
    assert "<h1>Default headline</h1>" in row["preview_html"]
    assert 'class="hero"' in row["preview_html"]          # className normalised
    assert body["meta"]["categories"] == ["hero"] and body["meta"]["total"] >= 1


@pytest.mark.high
async def test_patch_props_rerenders_escapes_and_clears_inline_edits(
    client: AsyncClient, admin_user: User, v2_page: Page, db: AsyncSession,
):
    # Simulate a prior inline edit that must be discarded.
    secs = json.loads(v2_page.sections_json)
    secs[0]["edited_html"] = "<section><h1>hand edited</h1></section>"
    v2_page.sections_json = json.dumps(secs)
    await db.commit()

    resp = await client.patch(
        f"/api/pages/{v2_page.id}/sections/0",
        headers=auth_header(admin_user),
        json={"props": {
            "HEADLINE": "  Plans & <script>alert(1)</script> rates ",
            "BULLETS": [{"VALUE": "A"}, {"VALUE": "<b>B</b>"}, {"VALUE": "C"}, {"VALUE": "D"}],
            "CTA_HREF": "javascript:alert(1)",
            "NOT_A_FIELD": "dropped",
        }},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sec = _first_section(body)
    props = sec["metadata"]["props"]
    assert props["HEADLINE"] == "Plans & alert(1) rates"       # tags stripped, whitespace collapsed
    assert props["BULLETS"] == [{"VALUE": "A"}, {"VALUE": "B"}, {"VALUE": "C"}]  # max_items=3
    assert "NOT_A_FIELD" not in props
    assert props["SUBHEADLINE"] == "Default sub"                # untouched field kept
    html = sec["jsx_content"]
    assert "<h1>Plans &amp; alert(1) rates</h1>" in html        # engine escapes v2 values
    assert '<li data-i="1">A</li><li data-i="2">B</li><li data-i="3">C</li>' in html
    assert 'href="{{CTA_HREF}}"' not in html and "javascript:" not in html
    assert sec["edited_html"] is None                          # inline edit discarded
    assert any(e.startswith("CTA_HREF:") for e in body.get("field_errors", []))
    # Page recompiled from the new render.
    assert "Plans &amp; alert(1) rates" in (body["data"].get("html_content") or "")


@pytest.mark.high
async def test_patch_props_rejects_non_library_sections(client: AsyncClient, admin_user: User, db: AsyncSession):
    p = Page(
        id=uuid.uuid4(), title="AI page", slug=f"ai-{uuid.uuid4().hex[:6]}", status=PageStatus.DRAFT,
        sections_json=json.dumps([{"id": "s1", "type": "hero", "jsx_content": "<section><h1>x</h1></section>"}]),
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    resp = await client.patch(
        f"/api/pages/{p.id}/sections/0", headers=auth_header(admin_user), json={"props": {"HEADLINE": "y"}},
    )
    assert resp.status_code == 400
    resp = await client.patch(
        f"/api/pages/{p.id}/sections/0", headers=auth_header(admin_user), json={"props": "nope"},
    )
    assert resp.status_code == 400


@pytest.mark.high
async def test_add_section_with_locale_uses_locale_props(
    client: AsyncClient, admin_user: User, v2_variant, db: AsyncSession,
):
    p = Page(id=uuid.uuid4(), title="fr page", slug=f"fr-{uuid.uuid4().hex[:6]}",
             status=PageStatus.DRAFT, sections_json="[]", created_by=admin_user.id)
    db.add(p)
    await db.commit()
    resp = await client.post(
        f"/api/pages/{p.id}/sections", headers=auth_header(admin_user),
        json={"category": "hero", "variant_id": "test_v2_hero", "locale": "fr-CA"},
    )
    assert resp.status_code in (200, 201), resp.text
    sec = _first_section(resp.json())
    assert "<h1>Titre par défaut</h1>" in sec["jsx_content"]
    assert sec["metadata"]["locale"] == "fr-CA"
    assert sec["metadata"]["motion_preset"] == "css_reveal_up"


def test_compile_emits_data_motion_and_css_only_when_used(v2_variant_dict=V2_SEED):
    from types import SimpleNamespace
    from app.pages.compiler import compile_page

    variant = SimpleNamespace(**{**v2_variant_dict, "default_animations": None,
                                 "preview_thumbnail_url": None, "svg_thumbnail": None,
                                 "data_source": None, "data_mode": None, "behaviour": None})
    with_motion = variant_to_section(variant)
    without = variant_to_section(SimpleNamespace(**{**vars(variant), "motion_preset": None}))

    def page_for(sections):
        return SimpleNamespace(
            id=uuid.uuid4(), title="m", slug="m", description=None, meta_title=None, meta_description=None,
            og_image_url=None, favicon_url=None, sections_json=json.dumps(sections),
            html_content=None, css_content=None, js_content=None, custom_head_html=None,
            created_by=None, website_id=None,
        )

    html = compile_page(page_for([with_motion]))
    assert 'data-motion="css_reveal_up"' in html
    assert '<style id="pages-motion">' in html and "pg-reveal-up" in html
    assert "@supports (animation-timeline: view())" in html
    assert "prefers-reduced-motion" in html

    html2 = compile_page(page_for([without]))
    assert "data-motion=" not in html2 and "pages-motion" not in html2
