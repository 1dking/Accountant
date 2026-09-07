"""Variant library service — token substitution + content migration.

Renders a SectionVariant template by substituting {{TOKEN}} placeholders
with values from default_props (override-able). Used by:
  - POST /sections   — inserting a new section from a variant
  - POST /sections/{idx}/change-variant — swapping variant on existing
    section, preserving content where tokens match
"""
from __future__ import annotations

import html as html_escape
import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pages.models import SectionVariant

logger = logging.getLogger(__name__)


_TOKEN_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

# Tokens whose substitution is DEFERRED until compile_page. The
# variant picker keeps these literal in jsx_content so users can swap
# the value via sections_json[i].media_overrides without re-rendering
# the entire template. compile_page does one final pass per section
# with (default_props ⊕ media_overrides).
#
# To extend: add a new token here and reference it in any variant
# template. No code change in compile_page or the editor is needed —
# the media drawer auto-detects {{X_URL}} occurrences in the rendered
# content.
MEDIA_TOKENS: frozenset[str] = frozenset({
    "VIDEO_URL",
    "VIDEO_POSTER_URL",
    "IMAGE_URL",
    "LOGO_URL",
    "MEDIA_URL",
})

# Element-level tokens — substitute to full HTML markup (not just a
# URL). Polymorphic: the rendered element depends on the URL pattern
# (YouTube → iframe, mp4 → <video>, image → <img>). These let a single
# slot accept any media type without changing the variant template.
#
# {{VIDEO_EMBED}}  — video player (video-only slots). Reads VIDEO_URL.
# {{MEDIA_EMBED}}  — flexible media (any media type). Reads MEDIA_URL.
EMBED_TOKENS: frozenset[str] = frozenset({"VIDEO_EMBED", "MEDIA_EMBED"})

# Each embed token reads its URL from this canonical media-props key.
# Used by the SectionEditor pill so PATCH writes under the right key.
EMBED_TOKEN_URL_KEY: dict[str, str] = {
    "VIDEO_EMBED": "VIDEO_URL",
    "MEDIA_EMBED": "MEDIA_URL",
}


# Full tag grammar (v2). Matches, in order of alternation:
#   {{{RAW}}}            raw (unescaped) value
#   {{#KEY}} … {{/KEY}}  section: list → repeat per item; truthy → once
#   {{^KEY}} … {{/KEY}}  inverted: render when missing/empty/false
#   {{KEY}}              value; {{@INDEX}} {{@FIRST}} {{@LAST}} inside loops
_TAG_RE = re.compile(
    r"\{\{\{\s*([A-Z0-9_@]+)\s*\}\}\}"            # 1: raw
    r"|\{\{\s*([#^/])\s*([A-Z0-9_]+)\s*\}\}"      # 2: sigil, 3: block key
    r"|\{\{\s*([A-Z0-9_@]+)\s*\}\}"                # 4: value
)


def _parse(template: str) -> list:
    """Parse into a tree: str | ("var", key, raw) | ("section", key, inverted, children).
    Unmatched closers are kept literal; an unclosed block runs to the end."""
    root: list = []
    stack: list[tuple[str, bool, list]] = []  # (key, inverted, children)
    pos = 0
    for m in _TAG_RE.finditer(template):
        if m.start() > pos:
            (stack[-1][2] if stack else root).append(template[pos:m.start()])
        pos = m.end()
        target = stack[-1][2] if stack else root
        if m.group(1):
            target.append(("var", m.group(1), True))
        elif m.group(2):
            sigil, key = m.group(2), m.group(3)
            if sigil == "/":
                if stack and stack[-1][0] == key:
                    key_, inverted, children = stack.pop()
                    (stack[-1][2] if stack else root).append(("section", key_, inverted, children))
                else:
                    target.append(m.group(0))  # stray closer stays literal
            else:
                stack.append((key, sigil == "^", []))
        else:
            target.append(("var", m.group(4), False))
    if pos < len(template):
        (stack[-1][2] if stack else root).append(template[pos:])
    while stack:  # unclosed block — treat as closed at end
        key_, inverted, children = stack.pop()
        (stack[-1][2] if stack else root).append(("section", key_, inverted, children))
    return root


def _lookup(key: str, ctx: list[dict]) -> Any:
    for frame in reversed(ctx):
        if key in frame and frame[key] is not None:
            return frame[key]
    return None


def _render_nodes(nodes: list, ctx: list[dict], skip: frozenset[str], escape: bool, out: list[str]) -> None:
    for node in nodes:
        if isinstance(node, str):
            out.append(node)
            continue
        if node[0] == "var":
            _, key, raw = node
            if key in skip:
                out.append("{{" + key + "}}")  # deferred to compile_page
                continue
            val = _lookup(key, ctx)
            if val is None:
                out.append("{{" + key + "}}")  # unresolved — keep visible
                continue
            if isinstance(val, bool):
                val = "true" if val else ""
            text = str(val)
            out.append(text if (raw or not escape) else html_escape.escape(text, quote=True))
            continue
        _, key, inverted, children = node
        val = _lookup(key, ctx)
        truthy = bool(val) and val != [] and val != {}
        if inverted:
            if not truthy:
                _render_nodes(children, ctx, skip, escape, out)
            continue
        if not truthy:
            continue
        if isinstance(val, list):
            n = len(val)
            for i, item in enumerate(val):
                frame = dict(item) if isinstance(item, dict) else {"VALUE": item}
                frame["@INDEX"] = i + 1
                frame["@FIRST"] = "true" if i == 0 else ""
                frame["@LAST"] = "true" if i == n - 1 else ""
                _render_nodes(children, ctx + [frame], skip, escape, out)
        elif isinstance(val, dict):
            _render_nodes(children, ctx + [dict(val)], skip, escape, out)
        else:
            _render_nodes(children, ctx, skip, escape, out)


def render_template(
    template: str,
    props: dict[str, Any],
    *,
    skip_tokens: frozenset[str] | None = None,
    escape: bool = False,
) -> str:
    """Substitute {{TOKEN}} occurrences (v1) plus, since block model v2,
    {{#LIST}}…{{/LIST}} loops, {{^KEY}} inverted sections, {{@INDEX}}/
    {{@FIRST}}/{{@LAST}} loop metadata and {{{RAW}}} unescaped values.

    Tokens in `skip_tokens` are left literal so a downstream pass
    (compile_page) can substitute them later. Unresolved tokens (missing
    from props AND not in skip_tokens) also stay literal so the user can
    fill them in via the inline editor.

    `escape=True` (v2 variants) HTML-escapes every substituted value —
    field values are copy, never markup. v1 callers keep raw behaviour.
    """
    skip = skip_tokens or frozenset()
    out: list[str] = []
    _render_nodes(_parse(template or ""), [dict(props or {})], skip, escape, out)
    return "".join(out)


def substitute_media_tokens(html: str, media_props: dict[str, Any]) -> str:
    """Final-pass substitution for media tokens. Called by compile_page
    for each section with the merged (default_props ⊕ media_overrides)
    values.

    Two flavors of token are handled here:
      - URL tokens (MEDIA_TOKENS): swap the literal {{VIDEO_URL}} →
        URL string. For simple slots like VIDEO_POSTER_URL where you
        want to substitute into an attribute (poster=, src=, etc.).
      - Element tokens (EMBED_TOKENS): swap {{VIDEO_EMBED}} →
        full <iframe>/<video>/<img> markup based on URL classification.
        Lets a single slot accept any media type — picker doesn't have
        to know what element the template uses.

    Non-media tokens and unresolved tokens stay literal.
    """
    if not html:
        return html
    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in EMBED_TOKENS:
            url_key = EMBED_TOKEN_URL_KEY.get(key)
            if not url_key:
                return match.group(0)
            url = media_props.get(url_key)
            if not url:
                return match.group(0)
            poster = media_props.get("VIDEO_POSTER_URL")
            slot_kind = "video" if key == "VIDEO_EMBED" else "media"
            return render_media_embed(
                str(url), poster_url=poster, kind=slot_kind,
            )
        if key in MEDIA_TOKENS:
            val = media_props.get(key)
            if val is None or val == "":
                return match.group(0)
            return str(val)
        return match.group(0)
    return _TOKEN_RE.sub(_sub, html)


def _strip_query(url: str) -> str:
    """Drop ?query and #fragment for extension matching."""
    if not url:
        return ""
    return url.split("?", 1)[0].split("#", 1)[0]


def _extract_youtube_id(url: str) -> str | None:
    """Pull the 11-char YouTube video ID from any common URL shape, or
    return None if the URL isn't a YouTube reference."""
    if not url:
        return None
    s = url.strip()
    # Bare ID
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = re.search(
        r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})",
        s,
    )
    return m.group(1) if m else None


def _extract_vimeo_id(url: str) -> str | None:
    """Pull the numeric Vimeo video ID from a vimeo.com URL, or None."""
    if not url:
        return None
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url.strip())
    return m.group(1) if m else None


# File extensions used by media URL pattern detection. Case-insensitive
# match is applied at the call site. Keep these conservative — anything
# else defaults to <img> with a logged warning.
_VIDEO_EXTS = (".mp4", ".webm", ".ogg", ".mov")
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif")


# Image-CDN hosts that serve image content without file extensions in
# the URL (Unsplash thumbnailer, etc.). When no extension matches but
# the URL is from one of these, treat as image. Keep tight — only add
# hosts we know are strictly image-serving.
_KNOWN_IMAGE_HOSTS = (
    "images.unsplash.com",
    "source.unsplash.com",
    "plus.unsplash.com",
    "res.cloudinary.com",
    "cdn.pixabay.com",
    "images.pexels.com",
)


def classify_media_url(url: str) -> str:
    """Detect what kind of media a URL represents. Returns one of:
      'youtube' / 'vimeo' / 'video' (direct file) / 'image' / 'unknown'.

    Order of checks matters: YouTube/Vimeo pattern beats file extension
    (a YouTube URL with /watch path has no .mp4). Falls back to a
    small known-image-host whitelist so extension-less Unsplash/etc.
    URLs classify correctly.
    """
    if not url:
        return "unknown"
    if _extract_youtube_id(url):
        return "youtube"
    if _extract_vimeo_id(url):
        return "vimeo"
    base = _strip_query(url).lower()
    if base.endswith(_VIDEO_EXTS):
        return "video"
    if base.endswith(_IMAGE_EXTS):
        return "image"
    # Extension-less? Check known image hosts.
    if any(host in url for host in _KNOWN_IMAGE_HOSTS):
        return "image"
    return "unknown"


def normalize_video_url(url: str) -> str:
    """Normalize a user-pasted video URL to a form that renders cleanly.

    - YouTube URL (any shape) → canonical embed URL with autoplay+
      mute+loop params.
    - Vimeo URL → canonical player.vimeo.com embed URL.
    - Direct video file (.mp4 etc.) → passed through unchanged.
    - Unknown shape → passed through unchanged (probably a direct URL
      we don't recognize).
    """
    if not url:
        return url
    s = url.strip()
    vid = _extract_youtube_id(s)
    if vid:
        return (
            f"https://www.youtube.com/embed/{vid}"
            f"?autoplay=1&mute=1&loop=1&playlist={vid}"
            f"&controls=0&rel=0&modestbranding=1"
        )
    vimeo_id = _extract_vimeo_id(s)
    if vimeo_id:
        return (
            f"https://player.vimeo.com/video/{vimeo_id}"
            f"?autoplay=1&muted=1&loop=1&background=1"
        )
    return s


def _html_attr_escape(v: str) -> str:
    """Conservative attribute-value escape. Avoid escaping the query
    string's & to &amp; would also work but the most common consumers
    (browsers parsing srcdoc/iframe src) handle either form."""
    return (
        v.replace("&", "&amp;")
         .replace('"', "&quot;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def render_media_embed(
    url: str, *, poster_url: str | None = None, alt: str = "", kind: str = "media",
) -> str:
    """Polymorphic media renderer. Returns the full HTML element for
    the URL based on its detected kind. Used to expand {{VIDEO_EMBED}}
    and {{MEDIA_EMBED}} at compile time.

    `kind` is the slot's declared semantic role — only used for the
    fallback default. 'media' defaults to <img> when ambiguous; 'video'
    defaults to <iframe> (the more common shape for video).
    """
    if not url:
        return ""
    detected = classify_media_url(url)
    safe_url = _html_attr_escape(url)
    safe_alt = _html_attr_escape(alt) if alt else ""
    safe_poster = _html_attr_escape(poster_url) if poster_url else ""
    if detected in ("youtube", "vimeo"):
        # Both render as iframe; the URL itself is already normalized
        # to the right embed shape via normalize_video_url at PATCH time.
        return (
            f'<iframe src="{safe_url}" '
            f'class="absolute inset-0 w-full h-full" '
            f'frameborder="0" '
            f'allow="autoplay; encrypted-media; picture-in-picture" '
            f'allowfullscreen></iframe>'
        )
    if detected == "video":
        poster_attr = f' poster="{safe_poster}"' if safe_poster else ""
        return (
            f'<video autoplay muted loop playsinline{poster_attr} '
            f'class="absolute inset-0 w-full h-full object-cover">'
            f'<source src="{safe_url}" /></video>'
        )
    if detected == "image":
        alt_attr = f' alt="{safe_alt}"' if safe_alt else ' alt=""'
        return (
            f'<img src="{safe_url}"{alt_attr} '
            f'class="absolute inset-0 w-full h-full object-cover" />'
        )
    # Unknown shape: default behavior depends on slot kind.
    # 'video' slots assume iframe (most YouTube-shaped URLs we don't
    # recognize). 'media' slots default to <img> — a broken image is
    # visible to the user, whereas a broken iframe is silent.
    logger.info(
        "media.url_classify_unknown url=%r slot_kind=%s — defaulting",
        url[:200], kind,
    )
    if kind == "video":
        return (
            f'<iframe src="{safe_url}" '
            f'class="absolute inset-0 w-full h-full" '
            f'frameborder="0" '
            f'allow="autoplay; encrypted-media" '
            f'allowfullscreen></iframe>'
        )
    alt_attr = f' alt="{safe_alt}"' if safe_alt else ' alt=""'
    return (
        f'<img src="{safe_url}"{alt_attr} '
        f'class="absolute inset-0 w-full h-full object-cover" />'
    )


# Backward-compat alias — kept for any tests or callers that imported
# the older YouTube-only normalizer. Forwards to the broader version.
def normalize_youtube_url(url: str) -> str:
    return normalize_video_url(url)


def extract_token_values(rendered_html: str, template: str) -> dict[str, str]:
    """Best-effort: given a rendered section's HTML and the template
    it came from, infer the {{TOKEN}} -> actual-value mapping by
    diffing positions.

    Approach: split template on token boundaries → for each pair of
    adjacent literal chunks, find the corresponding text between them
    in the rendered HTML and assign that substring to the token.

    This is intentionally simple — it works for clean substitutions
    (no nested tokens, no whitespace changes between literal chunks)
    and falls back to silently dropping tokens that can't be resolved.
    """
    if not rendered_html or not template:
        return {}
    parts = _TOKEN_RE.split(template)
    # parts alternates: [literal, token, literal, token, ..., literal]
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    cursor = 0
    for i in range(1, len(parts), 2):
        token = parts[i]
        before = parts[i - 1]
        after = parts[i + 1] if i + 1 < len(parts) else ""
        # find `before` starting from cursor
        before_idx = rendered_html.find(before, cursor)
        if before_idx < 0:
            continue
        value_start = before_idx + len(before)
        # find `after` after value_start. If `after` is empty, take
        # to end of html.
        if after:
            # Take the first non-empty literal chunk from `after` to
            # avoid matching whitespace-only boundaries.
            anchor = after.lstrip()[:32]
            if not anchor:
                continue
            after_idx = rendered_html.find(anchor, value_start)
            if after_idx < 0:
                continue
            value = rendered_html[value_start:after_idx].strip()
        else:
            value = rendered_html[value_start:].strip()
        if value and len(value) < 2000:
            out[token] = value
        cursor = value_start
    return out


async def get_variant(
    db: AsyncSession, category: str, variant_id: str,
) -> SectionVariant | None:
    """Fetch one variant by category + variant_id. Returns None if
    not found or inactive."""
    rows = await db.execute(
        select(SectionVariant).where(
            SectionVariant.category == category,
            SectionVariant.variant_id == variant_id,
            SectionVariant.is_active.is_(True),
        )
    )
    return rows.scalar_one_or_none()


async def list_variants(
    db: AsyncSession, category: str | None = None,
) -> list[SectionVariant]:
    """List active variants. If category is provided, filter to that
    category. Ordered by sort_order ASC, display_name ASC."""
    stmt = select(SectionVariant).where(SectionVariant.is_active.is_(True))
    if category:
        stmt = stmt.where(SectionVariant.category == category)
    stmt = stmt.order_by(SectionVariant.sort_order, SectionVariant.display_name)
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


def effective_props(
    variant: SectionVariant, *, locale: str = "en", prop_overrides: dict | None = None,
) -> tuple[dict, list[str]]:
    """default_props ⊕ locale_props[locale] ⊕ overrides, validated against
    fields_schema when the variant is v2. Returns (props, errors)."""
    props = dict(variant.default_props or {})
    locale_props = getattr(variant, "locale_props", None) or {}
    if locale and locale != "en" and isinstance(locale_props.get(locale), dict):
        props.update(locale_props[locale])
    props.update(prop_overrides or {})
    schema = getattr(variant, "fields_schema", None)
    errors: list[str] = []
    if schema:
        from app.pages.fields import validate_fields
        clean, errors = validate_fields(schema, props, locale=locale)
        schema_keys = {f["key"] for f in schema if f.get("key")}
        # Non-schema tokens (media, embeds, legacy) pass through untouched;
        # schema fields come only from the validated set (a rejected value
        # leaves its {{TOKEN}} visible rather than injecting raw input).
        props = {k: v for k, v in props.items() if k not in schema_keys}
        props.update(clean)
    return props, errors


def variant_to_section(
    variant: SectionVariant, *, prop_overrides: dict | None = None, locale: str = "en",
) -> dict:
    """Build a section dict ready to insert into sections_json from
    a variant + optional prop overrides. The result has:
      - id: uuid-based
      - type: derived from category
      - variant_id: which variant this came from
      - jsx_content: rendered template with MEDIA_TOKENS deferred
      - media_overrides: empty (user-supplied media values, applied
        at compile_page time)
      - metadata: full props snapshot — used by extract_token_values
        on subsequent variant swaps to migrate user content; for v2
        blocks it is the source of truth the fields panel edits.
    """
    props, _errors = effective_props(variant, locale=locale, prop_overrides=prop_overrides)
    is_v2 = int(getattr(variant, "schema_version", 1) or 1) >= 2
    rendered = render_template(
        variant.jsx_template, props,
        skip_tokens=MEDIA_TOKENS | EMBED_TOKENS,
        escape=is_v2,
    )
    # Snapshot the variant's animation config into the section so
    # compile_page (which is sync + DB-less) can read it without a
    # lookup. Future per-section overrides (Commit 4B) just modify
    # section['animations'] directly. Variant default updates apply
    # to NEW sections only — same lifecycle as metadata.props.
    section: dict = {
        "id": f"{variant.variant_id}-{uuid.uuid4().hex[:6]}",
        "type": variant.category,
        "title": variant.display_name,
        "summary": variant.description or "",
        "jsx_content": rendered,
        "media_overrides": {},
        "metadata": {
            "variant_id": variant.variant_id,
            "props": props,
            "schema_version": 2 if is_v2 else 1,
            "locale": locale,
        },
    }
    # v2 block metadata the compiler turns into data-block / data-motion
    # attributes (the runtime initialises behaviour modules from them).
    for attr in ("behaviour", "data_source", "data_mode", "motion_preset"):
        val = getattr(variant, attr, None)
        if val:
            section["metadata"][attr] = val
    # getattr-guarded so test fakes / older variant objects without
    # the field don't blow up (variant.default_animations was added
    # in migration b1c2d3e8).
    animations = getattr(variant, "default_animations", None)
    if animations:
        section["animations"] = animations
    return section


def _seed_values(v: dict) -> dict:
    """Column values for one seed dict (shared by seed_if_empty and
    resync_variants so the two never drift). v1 seeds without an explicit
    fields_schema get one inferred from default_props and are promoted to
    schema_version 2 — every library block is fields-driven and escaped."""
    from app.pages.fields import infer_fields_schema
    from app.pages.variant_svg_schematics import SCHEMATICS_BY_VARIANT_ID

    default_props = v.get("default_props", {}) or {}
    fields_schema = v.get("fields_schema") or infer_fields_schema(default_props)
    return {
        "display_name": v["display_name"],
        "description": v.get("description"),
        "jsx_template": v["jsx_template"],
        "default_props": default_props,
        "svg_thumbnail": SCHEMATICS_BY_VARIANT_ID.get(v["variant_id"]),
        "default_animations": v.get("default_animations"),
        "sort_order": v.get("sort_order", 100),
        "fields_schema": fields_schema,
        "schema_version": int(v.get("schema_version", 2)),
        "data_source": v.get("data_source"),
        "data_mode": v.get("data_mode"),
        "behaviour": v.get("behaviour"),
        "capabilities": v.get("capabilities"),
        "motion_preset": v.get("motion_preset"),
        "locale_props": v.get("locale_props"),
    }


async def seed_if_empty(db: AsyncSession) -> int:
    """Insert seed variants if the table is empty. Idempotent — does
    nothing once any rows exist. Returns count inserted."""
    from app.pages.variant_seeds import all_variants

    rows = await db.execute(select(SectionVariant).limit(1))
    if rows.first():
        return 0

    inserted = 0
    for v in all_variants():
        row = SectionVariant(
            id=v["id"],
            category=v["category"],
            variant_id=v["variant_id"],
            is_active=True,
            **_seed_values(v),
        )
        db.add(row)
        inserted += 1
    await db.commit()
    return inserted


async def fetch_variant_animations_for_page(
    db: AsyncSession, sections_json: str | None,
) -> dict[str, Any]:
    """Pre-fetch SectionVariant.default_animations for the variant_ids
    referenced by a page's sections. Used by callers that compile_page
    so legacy sections (which don't have their own snapshot) still
    light up with the variant's default animations. Zero-migration
    fallback path.

    Returns {variant_id → animation_config}. Empty dict if no variant
    ids found or all variants are animation-less.
    """
    if not sections_json:
        return {}
    try:
        sections = json.loads(sections_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(sections, list):
        return {}
    variant_ids = {
        (s.get("metadata") or {}).get("variant_id")
        for s in sections
        if isinstance(s, dict)
    }
    variant_ids.discard(None)
    if not variant_ids:
        return {}
    rows = await db.execute(
        select(SectionVariant.variant_id, SectionVariant.default_animations).where(
            SectionVariant.variant_id.in_(variant_ids),
            SectionVariant.is_active.is_(True),
        )
    )
    out: dict[str, Any] = {}
    for vid, anims in rows.all():
        if anims:
            out[vid] = anims
    return out


async def resync_variants(db: AsyncSession) -> int:
    """Re-sync seed data for variants that already exist. Updates
    jsx_template, default_props, svg_thumbnail, display_name, and
    description from variant_seeds — leaves is_active alone so admin
    disables stick. Returns number updated. Use after a code change
    that updates seed templates (e.g. the hero_video v3 video-bg fix)."""
    from app.pages.variant_seeds import all_variants

    updated = 0
    for v in all_variants():
        rows = await db.execute(
            select(SectionVariant).where(
                SectionVariant.category == v["category"],
                SectionVariant.variant_id == v["variant_id"],
            )
        )
        row = rows.scalar_one_or_none()
        values = _seed_values(v)
        if row is None:
            db.add(SectionVariant(
                id=v["id"],
                category=v["category"],
                variant_id=v["variant_id"],
                is_active=True,
                **values,
            ))
            updated += 1
            continue
        for col, val in values.items():
            setattr(row, col, val)
        updated += 1
    await db.commit()
    return updated
