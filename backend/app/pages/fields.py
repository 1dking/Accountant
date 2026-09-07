"""Block field schemas — the contract between a block template, the editor
and the AI.

A v2 variant declares `fields_schema`: an ordered list of field defs. Keys
are the uppercase {{TOKEN}} names used in `jsx_template`, so the existing
token engine, MEDIA_TOKENS and the SectionEditor media pills keep working.
Values come from three places and always pass through `validate_fields`
before they touch a section: the editor's fields panel (PATCH props), the
AI "fill" step, and `variant_to_section` at insert time.

Field def shape:
    {
      "key": "HEADLINE",              # uppercase token
      "type": "text",                 # text|textarea|number|color|url|select|boolean|image|list
      "label": "Headline", "label_fr": "Titre",
      "required": true, "max_len": 80,
      "default": "…",                 # optional; default_props wins when absent
      "options": ["grid","list"],     # select
      "options_from": "calendars",    # select whose choices the editor fetches
      "bind": "company.phone",        # default pulled from a data source
      "runtime": true,                # also emitted into data-block-config
      "min_items": 1, "max_items": 4, # list
      "item_fields": [ …field defs… ] # list
    }
"""
from __future__ import annotations

import html
import re
from typing import Any

FIELD_TYPES = frozenset({
    "text", "textarea", "number", "color", "url", "select", "boolean", "image", "list",
})
_TAG_RE = re.compile(r"<[^>]*>")
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_URL_RE = re.compile(r"^(https?://|mailto:|tel:|sms:|/|#)", re.IGNORECASE)


def field_label(field: dict, locale: str = "en") -> str:
    if locale.startswith("fr") and field.get("label_fr"):
        return field["label_fr"]
    return field.get("label") or field["key"].replace("_", " ").title()


def _strip_tags(value: str) -> str:
    # Values are inserted into templates by the engine, which escapes them
    # for v2; stripping tags here additionally keeps AI/user copy plain.
    return html.unescape(_TAG_RE.sub("", value))


def _coerce(field: dict, raw: Any, locale: str, errors: list[str], path: str) -> Any:
    ftype = field.get("type", "text")
    if raw is None:
        return None
    if ftype in ("text", "textarea", "url", "image", "color", "select"):
        if not isinstance(raw, str):
            raw = str(raw)
        val = raw.strip()
        if ftype in ("text", "textarea"):
            val = _strip_tags(val)
            if ftype == "text":
                val = " ".join(val.split())
            max_len = field.get("max_len")
            if max_len and len(val) > int(max_len):
                val = val[: int(max_len)].rstrip()
        elif ftype == "color":
            if val and not _HEX_RE.match(val):
                errors.append(f"{path}: not a hex color")
                return None
        elif ftype in ("url", "image"):
            if val and not _URL_RE.match(val) and not val.startswith("data:image/"):
                errors.append(f"{path}: not a URL")
                return None
        elif ftype == "select":
            options = field.get("options")
            if options and val not in options:
                errors.append(f"{path}: '{val}' is not one of {options}")
                return None
        return val
    if ftype == "number":
        try:
            num = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{path}: not a number")
            return None
        if "min" in field and num < field["min"]:
            num = float(field["min"])
        if "max" in field and num > field["max"]:
            num = float(field["max"])
        return int(num) if num.is_integer() else num
    if ftype == "boolean":
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)
    if ftype == "list":
        if not isinstance(raw, list):
            errors.append(f"{path}: expected a list")
            return None
        max_items = field.get("max_items")
        items_raw = raw[: int(max_items)] if max_items else raw
        item_fields = field.get("item_fields") or []
        items: list[dict] = []
        for i, item in enumerate(items_raw):
            if not isinstance(item, dict):
                errors.append(f"{path}[{i}]: expected an object")
                continue
            clean_item, item_errors = validate_fields(item_fields, item, locale=locale, _path=f"{path}[{i}].")
            errors.extend(item_errors)
            items.append(clean_item)
        min_items = field.get("min_items")
        if min_items and len(items) < int(min_items):
            errors.append(f"{path}: needs at least {min_items} item(s)")
        return items
    errors.append(f"{path}: unknown field type '{ftype}'")
    return None


def validate_fields(
    schema: list[dict] | None,
    values: dict[str, Any] | None,
    *,
    locale: str = "en",
    _path: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Coerce + validate `values` against `schema`.

    Returns (clean, errors). `clean` contains ONLY schema keys: coerced
    values, or the field's own `default` when the value is missing. Keys not
    in the schema are dropped (unknown tokens never reach a template).
    Required fields with no value and no default are reported in `errors`
    but do not raise — callers decide (the AI fill step retries, the editor
    shows the message, insert falls back to default_props).
    """
    errors: list[str] = []
    clean: dict[str, Any] = {}
    values = values or {}
    for field in schema or []:
        key = field.get("key")
        if not key:
            continue
        path = f"{_path}{key}"
        raw = values.get(key, None)
        if raw is None or raw == "" or raw == []:
            if "default" in field:
                clean[key] = field["default"]
            elif field.get("required"):
                errors.append(f"{path}: required")
            elif raw is not None:
                clean[key] = raw  # explicit empty is a valid value for an optional field
            continue
        val = _coerce(field, raw, locale, errors, path)
        if val is not None:
            clean[key] = val
        elif "default" in field:
            clean[key] = field["default"]
    return clean, errors


def infer_fields_schema(default_props: dict[str, Any] | None) -> list[dict]:
    """Derive a fields_schema for a legacy v1 seed from its default_props.
    Key suffix decides the type: _HREF → url, _URL → image (video/poster
    URLs stay url), lists → list of inferred item fields, bools → boolean,
    numbers → number, long strings → textarea, else text."""
    schema: list[dict] = []
    for key, val in (default_props or {}).items():
        f: dict[str, Any] = {"key": key, "label": key.replace("_", " ").title()}
        if isinstance(val, bool):
            f["type"] = "boolean"
        elif isinstance(val, (int, float)):
            f["type"] = "number"
        elif isinstance(val, list):
            f["type"] = "list"
            first = next((x for x in val if isinstance(x, dict)), None)
            f["item_fields"] = infer_fields_schema(first) if first else [{"key": "VALUE", "type": "text"}]
        elif key.endswith("_HREF") or key in ("VIDEO_URL", "VIDEO_POSTER_URL", "MEDIA_URL"):
            f["type"] = "url"
        elif key.endswith("_URL"):
            f["type"] = "image"
        elif key.endswith("_COLOR"):
            f["type"] = "color"
        else:
            text = str(val or "")
            f["type"] = "textarea" if len(text) > 80 else "text"
            f["max_len"] = 600 if f["type"] == "textarea" else 160
        schema.append(f)
    return schema


def runtime_fields(schema: list[dict] | None, props: dict[str, Any]) -> dict[str, Any]:
    """Subset of props flagged `runtime: true` — emitted into the block's
    data-block-config so the page runtime can read them without parsing HTML."""
    out: dict[str, Any] = {}
    for field in schema or []:
        if field.get("runtime") and field.get("key") in props:
            out[field["key"]] = props[field["key"]]
    return out


def schema_tokens(schema: list[dict] | None) -> set[str]:
    return {f["key"] for f in (schema or []) if f.get("key")}


def ai_schema_summary(schema: list[dict] | None) -> list[dict]:
    """Compact view of a schema for the planner prompt: key, type, hint,
    limits, list item keys. Labels are dropped (the AI writes copy, not UI)."""
    out = []
    for f in schema or []:
        entry: dict[str, Any] = {"key": f["key"], "type": f.get("type", "text")}
        for k in ("required", "max_len", "max_items", "min_items", "options"):
            if k in f:
                entry[k] = f[k]
        if f.get("hint"):
            entry["hint"] = f["hint"]
        if f.get("type") == "list":
            entry["item_fields"] = ai_schema_summary(f.get("item_fields"))
        out.append(entry)
    return out
