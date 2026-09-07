"""Section backgrounds (image/video/gradient + overlay) and copy-only AI refine."""
import json
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages import conversational
from app.pages.compiler import compile_page, normalize_background, render_background_layer
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.seeds.dynamic_blocks import DYNAMIC_BLOCKS
from app.pages.variants import _seed_values, variant_to_section
from tests.conftest import auth_header


def _page(sections):
    return SimpleNamespace(id=uuid.uuid4(), title="m", slug="m", description=None, meta_title=None, meta_description=None,
                           og_image_url=None, favicon_url=None, sections_json=json.dumps(sections), html_content=None,
                           css_content=None, js_content=None, custom_head_html=None, created_by=None, website_id=None)


def test_normalize_background_rejects_bad_and_clamps():
    assert normalize_background(None) is None and normalize_background({"type": "none"}) is None
    assert normalize_background({"type": "image"}) is None                      # no url
    assert normalize_background({"type": "image", "url": "javascript:alert(1)"}) is None
    assert normalize_background({"type": "gradient", "gradient": "url(x)"}) is None
    bg = normalize_background({"type": "image", "url": "https://x/a.jpg", "overlay_opacity": 4, "overlay_color": "red", "position": "diagonal", "blur": 99})
    assert bg == {"type": "image", "url": "https://x/a.jpg", "overlay_opacity": 1.0, "position": "center", "parallax": False, "fixed": False, "blur": 20}


def test_hosted_video_backgrounds_render_as_cover_iframes():
    from app.pages.variants import normalize_video_url
    yt = render_background_layer({"type": "video", "url": normalize_video_url("https://youtu.be/dQw4w9WgXcQ"), "poster": "https://cdn/p.jpg"})
    assert "<iframe" in yt and "<video" not in yt
    assert "youtube.com/embed/dQw4w9WgXcQ?autoplay=1&amp;mute=1&amp;loop=1&amp;playlist=dQw4w9WgXcQ" in yt
    assert "playsinline=1" in yt and 'allow="autoplay; encrypted-media"' in yt and "pointer-events:none" in yt
    # chrome counters: oversize, hover shield after the frame, delayed fade-in
    assert "width:max(160%,285vh)" in yt and "animation:pg-bgin .8s ease 2.5s forwards" in yt
    assert yt.index("</iframe>") < yt.index('<div style="position:absolute;inset:0" aria-hidden="true"></div>')
    assert 'src="https://cdn/p.jpg"' in yt                                        # poster shows until the player starts
    vm = render_background_layer({"type": "video", "url": normalize_video_url("https://vimeo.com/123456")})
    assert "player.vimeo.com/video/123456" in vm and "background=1" in vm and "<iframe" in vm
    mp4 = render_background_layer({"type": "video", "url": "https://cdn/x.mp4"})
    assert "<video autoplay muted loop playsinline" in mp4 and "<iframe" not in mp4


def test_background_layer_and_compile_wrapping():
    layer = render_background_layer({"type": "video", "url": "https://cdn/x.mp4", "poster": "https://cdn/p.jpg", "overlay_color": "#0f172a", "overlay_opacity": 0.5})
    assert "<video autoplay muted loop playsinline" in layer and 'poster="https://cdn/p.jpg"' in layer
    assert "opacity:0.50" in layer and "background:#0f172a" in layer
    esc = render_background_layer({"type": "image", "url": 'https://cdn/a.jpg" onerror="x'})
    assert 'onerror=' not in esc.replace("&quot;", "") or "&quot;" in esc

    sec = {"id": "s1", "type": "hero", "jsx_content": "<section><h1>Hi</h1></section>",
           "background": {"type": "image", "url": "https://cdn/a.jpg", "parallax": True, "overlay_opacity": 0.3}}
    html = compile_page(_page([sec]))
    assert '<section id="section-s1" data-pages-section style="position:relative" data-motion="css_parallax_slow">' in html
    assert '<div class="pg-bg"' in html and "data-parallax" in html
    assert '<div class="pg-bg-content" style="position:relative;z-index:1"><section><h1>Hi</h1></section></div>' in html
    assert "pages-motion" in html and "runtime.js" in html                     # parallax needs the CSS preset + fallback
    assert "#section-s1 .pg-bg-content > *:first-child{background:transparent !important}" in html
    plain = compile_page(_page([{"id": "s2", "type": "hero", "jsx_content": "<section>x</section>"}]))
    assert "pg-bg" not in plain and 'style="position:relative"' not in plain


@pytest.mark.high
async def test_patch_background_validates_and_normalizes_video(client: AsyncClient, admin_user: User, db: AsyncSession):
    p = Page(id=uuid.uuid4(), title="bg", slug=f"bg-{uuid.uuid4().hex[:6]}", status=PageStatus.DRAFT,
             sections_json=json.dumps([{"id": "s1", "type": "hero", "jsx_content": "<section><h1>x</h1></section>"}]), created_by=admin_user.id)
    db.add(p)
    await db.commit()
    r = await client.patch(f"/api/pages/{p.id}/sections/0", headers=auth_header(admin_user),
                           json={"background": {"type": "video", "url": "https://www.youtube.com/watch?v=abc123xyz00", "overlay_opacity": 0.6}})
    assert r.status_code == 200, r.text
    sec = json.loads(r.json()["data"]["sections_json"])[0]
    assert sec["background"]["type"] == "video" and sec["background"]["overlay_opacity"] == 0.6
    assert "abc123xyz00" in sec["background"]["url"]
    assert "pg-bg" in (r.json()["data"].get("html_content") or "")
    r = await client.patch(f"/api/pages/{p.id}/sections/0", headers=auth_header(admin_user), json={"background": {"type": "image", "url": "javascript:x"}})
    assert r.status_code == 400
    r = await client.patch(f"/api/pages/{p.id}/sections/0", headers=auth_header(admin_user), json={"background": None})
    assert r.status_code == 200 and "background" not in json.loads(r.json()["data"]["sections_json"])[0]


@pytest_asyncio.fixture
async def lead_block(db: AsyncSession) -> SectionVariant:
    v = next(x for x in DYNAMIC_BLOCKS if x["variant_id"] == "contact_lead_form")
    row = SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v))
    db.add(row)
    await db.commit()
    return row


@pytest.mark.high
async def test_refine_copy_changes_words_only(client: AsyncClient, admin_user: User, db: AsyncSession, lead_block, monkeypatch):
    section = variant_to_section(lead_block)
    section["edited_html"] = "<section>hand edit</section>"
    original_template = lead_block.jsx_template
    p = Page(id=uuid.uuid4(), title="rf", slug=f"rf-{uuid.uuid4().hex[:6]}", status=PageStatus.DRAFT,
             sections_json=json.dumps([section]), created_by=admin_user.id)
    db.add(p)
    await db.commit()

    captured = {}

    async def fake_claude(settings, model, system_prompt, user_msg, max_tokens, timeout):
        captured["system"] = system_prompt
        captured["user"] = user_msg
        return {
            "HEADLINE": "Ottawa bookkeeping, <b>done right</b>",
            "SUBMIT_TEXT": "Book my free call",
            "EMAIL_ADDRESS": "evil@attacker.example",      # url/email-ish? it's text — allowed
            "PHONE_NUMBER": "555",                          # text — allowed
            "SIDE_TEXT": "x" * 5000,                        # clamped by max_len
            "NOT_A_FIELD": "dropped",
        }

    monkeypatch.setattr(conversational, "_claude_call_json", fake_claude)
    monkeypatch.setattr(conversational.Settings, "anthropic_api_key", "test-key", raising=False)

    r = await client.post(f"/api/pages/{p.id}/sections/0/refine", headers=auth_header(admin_user), json={"instruction": "Make it about Ottawa and punchier"})
    assert r.status_code == 200, r.text
    sec = json.loads(r.json()["data"]["sections_json"])[0]
    props = sec["metadata"]["props"]
    assert props["HEADLINE"] == "Ottawa bookkeeping, done right"          # tags stripped
    assert props["SUBMIT_TEXT"] == "Book my free call"
    assert len(props["SIDE_TEXT"]) <= 200 and "NOT_A_FIELD" not in props
    assert sec["edited_html"] is None                                     # re-rendered from template
    assert "Ottawa bookkeeping, done right" in sec["jsx_content"]
    assert 'data-lead-form' in sec["jsx_content"]                         # markup untouched
    assert sec["metadata"]["provider"] == "claude" and sec["metadata"]["variant_id"] == "contact_lead_form"
    assert "never write HTML" in captured["system"] and "Field schema" in captured["user"]
    # the block template itself was not modified
    await db.refresh(lead_block)
    assert lead_block.jsx_template == original_template
