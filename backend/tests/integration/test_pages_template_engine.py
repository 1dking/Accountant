"""Block model v2 — template engine + field validation (pure, no DB)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pages.fields import ai_schema_summary, runtime_fields, validate_fields
from app.pages.variants import MEDIA_TOKENS, effective_props, render_template, variant_to_section


# ---------------------------------------------------------------- engine ---

def test_v1_parity_simple_tokens_and_unresolved_stay_literal():
    out = render_template("<h1>{{HEADLINE}}</h1><p>{{ MISSING }}</p>", {"HEADLINE": "Hi"})
    assert out == "<h1>Hi</h1><p>{{MISSING}}</p>"


def test_v1_does_not_escape_values():
    out = render_template("<p>{{BODY}}</p>", {"BODY": "<b>bold</b>"})
    assert out == "<p><b>bold</b></p>"


def test_v2_escapes_values_but_triple_brace_is_raw():
    tpl = "<p>{{BODY}}</p><div>{{{RAW_HTML}}}</div>"
    out = render_template(tpl, {"BODY": "<script>x</script>", "RAW_HTML": "<em>ok</em>"}, escape=True)
    assert out == "<p>&lt;script&gt;x&lt;/script&gt;</p><div><em>ok</em></div>"


def test_skip_tokens_stay_literal_for_compile_pass():
    tpl = '<img src="{{IMAGE_URL}}"/><h1>{{HEADLINE}}</h1>'
    out = render_template(tpl, {"IMAGE_URL": "x.png", "HEADLINE": "H"}, skip_tokens=MEDIA_TOKENS)
    assert out == '<img src="{{IMAGE_URL}}"/><h1>H</h1>'


def test_list_loop_with_index_first_last():
    tpl ="<ul>{{#ITEMS}}<li data-i=\"{{@INDEX}}\" data-first=\"{{@FIRST}}\" data-last=\"{{@LAST}}\">{{NAME}}</li>{{/ITEMS}}</ul>"
    out = render_template(tpl, {"ITEMS": [{"NAME": "A"}, {"NAME": "B"}, {"NAME": "C"}]}, escape=True)
    assert out == (
        '<ul><li data-i="1" data-first="true" data-last="">A</li>'
        '<li data-i="2" data-first="" data-last="">B</li>'
        '<li data-i="3" data-first="" data-last="true">C</li></ul>'
    )


def test_loop_over_scalars_exposes_value():
    out = render_template("{{#TAGS}}[{{VALUE}}]{{/TAGS}}", {"TAGS": ["x", "y"]})
    assert out == "[x][y]"


def test_nested_loops_and_outer_context_visible_inside():
    tpl = "{{#PLANS}}<h3>{{NAME}} {{CURRENCY}}</h3>{{#FEATURES}}<li>{{VALUE}}</li>{{/FEATURES}}{{/PLANS}}"
    props = {"CURRENCY": "CAD", "PLANS": [{"NAME": "Basic", "FEATURES": ["a", "b"]}, {"NAME": "Pro", "FEATURES": []}]}
    out = render_template(tpl, props)
    assert out == "<h3>Basic CAD</h3><li>a</li><li>b</li><h3>Pro CAD</h3>"


def test_truthy_scalar_section_renders_once_and_inverted_when_empty():
    tpl = "{{#SHOW_BADGE}}<span>{{BADGE}}</span>{{/SHOW_BADGE}}{{^SHOW_BADGE}}<i>none</i>{{/SHOW_BADGE}}"
    assert render_template(tpl, {"SHOW_BADGE": True, "BADGE": "New"}) == "<span>New</span>"
    assert render_template(tpl, {"SHOW_BADGE": False, "BADGE": "New"}) == "<i>none</i>"
    assert render_template(tpl, {"BADGE": "New"}) == "<i>none</i>"
    assert render_template(tpl, {"SHOW_BADGE": [], "BADGE": "New"}) == "<i>none</i>"


def test_dict_section_pushes_context():
    out = render_template("{{#OWNER}}{{NAME}}/{{ROLE}}{{/OWNER}}", {"OWNER": {"NAME": "N", "ROLE": "CEO"}})
    assert out == "N/CEO"


def test_unclosed_and_stray_closers_are_tolerated():
    assert render_template("{{#A}}x{{VALUE}}", {"A": ["1"]}) == "x1"
    assert render_template("y{{/A}}", {}) == "y{{/A}}"


def test_boolean_values_render_as_true_or_empty():
    assert render_template("[{{ON}}][{{OFF}}]", {"ON": True, "OFF": False}) == "[true][]"


def test_v2_escapes_inside_loops_too():
    out = render_template("{{#L}}{{VALUE}}{{/L}}", {"L": ["<x>"]}, escape=True)
    assert out == "&lt;x&gt;"


# ---------------------------------------------------------------- fields ---

SCHEMA = [
    {"key": "HEADLINE", "type": "text", "required": True, "max_len": 10},
    {"key": "BODY", "type": "textarea", "default": "Default body"},
    {"key": "ACCENT", "type": "color", "default": "#123456"},
    {"key": "CTA_HREF", "type": "url"},
    {"key": "LAYOUT", "type": "select", "options": ["grid", "list"], "default": "grid"},
    {"key": "COUNT", "type": "number", "min": 1, "max": 5, "runtime": True},
    {"key": "SHOW", "type": "boolean"},
    {"key": "IMAGE_URL", "type": "image"},
    {
        "key": "ITEMS", "type": "list", "min_items": 1, "max_items": 2,
        "item_fields": [
            {"key": "NAME", "type": "text", "required": True},
            {"key": "PRICE", "type": "number"},
        ],
    },
]


def test_validate_coerces_clamps_and_defaults():
    clean, errors = validate_fields(SCHEMA, {
        "HEADLINE": "  A <b>very</b> long headline here ",
        "CTA_HREF": "https://x.ca/a",
        "COUNT": "12",
        "SHOW": "yes",
        "IMAGE_URL": "/api/settings/company/logo",
        "ITEMS": [{"NAME": "One", "PRICE": "9.5"}, {"NAME": "Two"}, {"NAME": "Three"}],
        "UNKNOWN": "dropped",
    })
    assert errors == []
    assert clean["HEADLINE"] == "A very lon"           # tags stripped, whitespace collapsed, clamped to 10
    assert clean["BODY"] == "Default body"
    assert clean["ACCENT"] == "#123456"
    assert clean["LAYOUT"] == "grid"
    assert clean["COUNT"] == 5                          # clamped to max
    assert clean["SHOW"] is True
    assert clean["ITEMS"] == [{"NAME": "One", "PRICE": 9.5}, {"NAME": "Two"}]  # max_items=2
    assert "UNKNOWN" not in clean
    assert "CTA_HREF" in clean and "IMAGE_URL" in clean


def test_validate_reports_required_and_bad_values_without_raising():
    clean, errors = validate_fields(SCHEMA, {
        "ACCENT": "red",
        "CTA_HREF": "javascript:alert(1)",
        "LAYOUT": "carousel",
        "COUNT": "lots",
        "ITEMS": [],
    })
    assert "HEADLINE: required" in errors
    assert any(e.startswith("ACCENT:") for e in errors)
    assert any(e.startswith("CTA_HREF:") for e in errors)
    assert any(e.startswith("LAYOUT:") for e in errors)
    assert any(e.startswith("COUNT:") for e in errors)
    # bad values fall back to the field default when there is one
    assert clean["ACCENT"] == "#123456"
    assert clean["LAYOUT"] == "grid"
    assert "CTA_HREF" not in clean and "COUNT" not in clean


def test_nested_list_item_errors_are_pathed():
    _, errors = validate_fields(SCHEMA, {"HEADLINE": "H", "ITEMS": [{"PRICE": 1}]})
    assert "ITEMS[0].NAME: required" in errors


def test_runtime_fields_and_ai_summary():
    assert runtime_fields(SCHEMA, {"COUNT": 3, "HEADLINE": "x"}) == {"COUNT": 3}
    summary = ai_schema_summary(SCHEMA)
    keys = [s["key"] for s in summary]
    assert keys[0] == "HEADLINE" and "label" not in summary[0]
    items = next(s for s in summary if s["key"] == "ITEMS")
    assert [f["key"] for f in items["item_fields"]] == ["NAME", "PRICE"]


# ------------------------------------------------------- variant_to_section ---

def _fake_variant(**over):
    base = dict(
        id="var_t", category="pricing", variant_id="pricing_v2_test", display_name="T",
        description="test variant",
        jsx_template=(
            '<section><h2>{{HEADLINE}}</h2><img src="{{IMAGE_URL}}"/>'
            "{{#PLANS}}<div data-i=\"{{@INDEX}}\"><h3>{{NAME}}</h3></div>{{/PLANS}}</section>"
        ),
        default_props={
            "HEADLINE": "Plans & <b>Rates</b>",
            "IMAGE_URL": "https://img/x.webp",
            "PLANS": [{"NAME": "Basic"}, {"NAME": "Pro"}],
        },
        default_animations=None, preview_thumbnail_url=None, svg_thumbnail=None,
        fields_schema=[
            {"key": "HEADLINE", "type": "text", "required": True},
            {"key": "IMAGE_URL", "type": "image"},
            {"key": "PLANS", "type": "list", "item_fields": [{"key": "NAME", "type": "text"}]},
        ],
        locale_props={"fr-CA": {"HEADLINE": "Forfaits"}},
        schema_version=2, behaviour="pricing_toggle", data_source="products",
        data_mode="compile", motion_preset="css_reveal_up",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_variant_to_section_v2_escapes_loops_defers_media_and_carries_metadata():
    section = variant_to_section(_fake_variant())
    html = section["jsx_content"]
    assert "<h2>Plans &amp; Rates</h2>" in html                # tags stripped by the field, & escaped by the engine
    assert 'src="{{IMAGE_URL}}"' in html                    # media deferred to compile
    assert '<div data-i="1"><h3>Basic</h3></div><div data-i="2"><h3>Pro</h3></div>' in html
    meta = section["metadata"]
    assert meta["schema_version"] == 2 and meta["locale"] == "en"
    assert meta["behaviour"] == "pricing_toggle"
    assert meta["data_source"] == "products" and meta["data_mode"] == "compile"
    assert meta["motion_preset"] == "css_reveal_up"
    assert meta["props"]["PLANS"] == [{"NAME": "Basic"}, {"NAME": "Pro"}]


def test_variant_to_section_locale_props_override_default_copy():
    section = variant_to_section(_fake_variant(), locale="fr-CA")
    assert "<h2>Forfaits</h2>" in section["jsx_content"]
    assert section["metadata"]["locale"] == "fr-CA"
    # overrides beat locale copy
    section = variant_to_section(_fake_variant(), locale="fr-CA", prop_overrides={"HEADLINE": "X"})
    assert "<h2>X</h2>" in section["jsx_content"]


def test_effective_props_validates_and_keeps_non_schema_tokens():
    v = _fake_variant(default_props={"HEADLINE": "H", "IMAGE_URL": "/u.png", "PLANS": [], "LEGACY": "kept"})
    props, errors = effective_props(v, prop_overrides={"HEADLINE": "<i>x</i>"})
    assert errors == []
    assert props["HEADLINE"] == "x" and props["LEGACY"] == "kept"


def test_v1_variant_still_renders_raw():
    v = _fake_variant(schema_version=1, fields_schema=None, locale_props=None,
                      behaviour=None, data_source=None, data_mode=None, motion_preset=None)
    section = variant_to_section(v)
    assert "Plans & <b>Rates</b>" in section["jsx_content"]
    assert section["metadata"]["schema_version"] == 1
    assert "behaviour" not in section["metadata"]
