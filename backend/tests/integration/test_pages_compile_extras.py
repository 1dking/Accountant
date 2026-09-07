"""Static compiler regressions fixed in the page-builder S0 sprint.

P1: css_content / js_content / custom_head_html / tracking + analytics
    (via extra_*) were dropped by compile_page — the legacy /public/view
    route emitted them, so a published page silently lost its pixels and
    the starter templates lost their @media rules.
P5: a variant mixing a 4B `preset` with 4A flat arrays (stats_4col_horizontal:
    fade_up + counter_up) lost the counters at compile time.
P6: user-edited and AI-generated section HTML shipped <script> verbatim.
"""

import json
import uuid
from types import SimpleNamespace

from app.pages.compiler import compile_page, sanitize_untrusted_html


def _page(**over):
    base = dict(
        id=uuid.uuid4(), title="T", slug="t", meta_title=None, meta_description=None,
        description=None, sections_json=None, html_content=None, css_content=None,
        js_content=None, custom_head_html=None, og_image_url=None, favicon_url=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_compile_emits_page_css_js_head_and_extras():
    page = _page(
        html_content="<section>hi</section>",
        css_content="@media (max-width:768px){.x{display:none}}",
        js_content="console.log('page-js')",
        custom_head_html='<meta name="x-custom" content="1">',
    )
    html = compile_page(
        page,
        extra_head="<!--pixel-head-->",
        extra_body_start="<!--pixel-body-start-->",
        extra_body_end="<!--analytics-beacon-->",
    )
    head, body = html.split("<body", 1)
    assert "@media (max-width:768px)" in head
    assert '<meta name="x-custom"' in head
    assert "<!--pixel-head-->" in head
    assert "console.log('page-js')" in body
    assert "<!--pixel-body-start-->" in body
    assert "<!--analytics-beacon-->" in body
    # Order: body-start before content, beacon last.
    assert body.index("<!--pixel-body-start-->") < body.index("<section>hi</section>")
    assert body.index("console.log('page-js')") < body.index("<!--analytics-beacon-->")


def test_compile_without_extras_is_clean():
    html = compile_page(_page(html_content="<p>x</p>"))
    assert "<style></style>" not in html
    assert "<script></script>" not in html


def test_mixed_preset_and_flat_animation_keeps_counters():
    sec = {
        "id": "s1",
        "jsx_content": '<div className="stat-value">500+</div>',
        "metadata": {"variant_id": "stats_4col_horizontal"},
        "animations": {
            "preset": "fade_up",
            "config": {"duration": 0.7},
            "counter_up": [{"selector": ".stat-value", "duration": 1.5}],
        },
    }
    html = compile_page(_page(sections_json=json.dumps([sec])))
    assert 'data-anim-preset="fade_up"' in html
    assert "data-section-anim=" in html and "counter_up" in html
    assert "gsap" in html.lower()


def test_untrusted_edited_html_is_sanitized_but_styles_survive():
    sec = {
        "id": "s1",
        "jsx_content": "<section>orig</section>",
        "edited_html": (
            '<section class="p-4" style="color:red">'
            '<style>.m{animation:x 1s}</style>'
            '<a href="javascript:alert(1)" onclick="evil()">x</a>'
            '<script>steal()</script>'
            '<svg viewBox="0 0 10 10"><path d="M0 0h10"/></svg>'
            '<iframe src="https://www.youtube.com/embed/abc" allowfullscreen></iframe>'
            "</section>"
        ),
        "metadata": {"variant_id": "hero_video"},
    }
    html = compile_page(_page(sections_json=json.dumps([sec])))
    assert "steal()" not in html and "<script>steal" not in html
    assert "onclick" not in html
    assert "javascript:" not in html
    assert '<style>.m{animation:x 1s}</style>' in html
    assert 'style="color:red"' in html
    assert 'viewBox="0 0 10 10"' in html
    assert 'src="https://www.youtube.com/embed/abc"' in html


def test_ai_section_without_variant_is_sanitized_but_library_section_is_not():
    ai = {"id": "a", "jsx_content": '<div onmouseover="x()">ai</div><script>z()</script>', "metadata": {}}
    lib = {"id": "l", "jsx_content": '<nav><script>window.__navScroll=1</script></nav>',
           "metadata": {"variant_id": "nav_solid_always"}}
    html = compile_page(_page(sections_json=json.dumps([ai, lib])))
    assert "onmouseover" not in html and "z()" not in html
    assert "window.__navScroll=1" in html  # trusted library script kept (moves to runtime in S2)


def test_sanitizer_idempotent_on_clean_html():
    clean = '<section class="a" data-x="1" aria-label="l"><p>Hi <b>there</b></p></section>'
    assert sanitize_untrusted_html(clean) == clean
