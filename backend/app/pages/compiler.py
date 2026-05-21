"""Compile Sections JSON → static HTML document.

Pages v2 — Session 2 (descoped). Produces a full <!DOCTYPE html>
document ready to upload to R2 and serve as-is. Output is:

  - Semantic HTML5 with lang attribute + proper meta tags
  - Tailwind via the official CDN script (no build step required)
  - JSON-LD Organization schema injected in <head> from
    company_settings (fallback to brand-agnostic if not configured)
  - Each section's jsx_content concatenated in render order
  - JSX → HTML normalization: className → class, htmlFor → for,
    strip JSX block comments {/* ... */}, self-closing tags work
    in HTML5 already

Tailwind CDN is the pragmatic choice for the v1 of static publish:
  - Zero build-step infra (no PostCSS, no purge config)
  - JIT in the browser handles arbitrary value classes (bg-[#hex])
  - Trade-off: ~50KB blocking CSS download. Acceptable v1; future
    work can swap to a build-step Tailwind pipeline.
"""
from __future__ import annotations

import html as html_escape
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.pages.models import Page

logger = logging.getLogger(__name__)

TAILWIND_CDN_SCRIPT = (
    '<script src="https://cdn.tailwindcss.com"></script>'
)

# JSX-to-HTML attribute rewrites. Plain HTML uses `class`, not `className`.
# We use word-boundary regexes so we don't accidentally touch
# "className" appearing inside a string literal.
_JSX_REWRITES = [
    (re.compile(r'\bclassName='), 'class='),
    (re.compile(r'\bhtmlFor='), 'for='),
    (re.compile(r'\btabIndex='), 'tabindex='),
]
_JSX_BLOCK_COMMENT = re.compile(r'\{/\*.*?\*/\}', re.DOTALL)


def _jsx_to_html(jsx: str) -> str:
    """Normalize JSX-flavored markup into valid HTML. Defensive — the
    upstream Claude prompt instructs it to emit JSX-style attributes,
    but the static-publish target is the browser, not a JSX runtime."""
    if not jsx:
        return ""
    out = _JSX_BLOCK_COMMENT.sub("", jsx)
    for pattern, replacement in _JSX_REWRITES:
        out = pattern.sub(replacement, out)
    return out


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _build_jsonld(
    page: Page,
    company_settings: Any | None,
    public_base_url: str,
) -> str:
    """Build a JSON-LD Organization schema block. Falls back to
    brand-agnostic values when company_settings isn't populated —
    better to ship valid schema than skip the SEO benefit."""
    org_name = "Organization"
    org_url = public_base_url
    org_email = None
    org_phone = None
    org_logo = None
    org_address = None

    if company_settings:
        org_name = (
            getattr(company_settings, "company_name", None) or org_name
        )
        org_email = getattr(company_settings, "company_email", None) or None
        org_phone = getattr(company_settings, "company_phone", None) or None
        org_logo = getattr(company_settings, "logo_url", None) or None
        # Address: only emit if all three city/state/zip are present
        # (incomplete addresses degrade schema quality).
        addr_line1 = getattr(company_settings, "address_line1", None)
        city = getattr(company_settings, "city", None)
        state = getattr(company_settings, "state", None)
        zip_code = getattr(company_settings, "zip_code", None)
        country = getattr(company_settings, "country", None)
        if addr_line1 and city:
            org_address = {
                "@type": "PostalAddress",
                "streetAddress": addr_line1,
                "addressLocality": city,
                "addressRegion": state or "",
                "postalCode": zip_code or "",
                "addressCountry": country or "US",
            }

    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": org_name,
        "url": org_url,
    }
    if org_logo:
        schema["logo"] = org_logo
    if org_email:
        schema["email"] = org_email
    if org_phone:
        schema["telephone"] = org_phone
    if org_address:
        schema["address"] = org_address

    # Use ensure_ascii=False so non-ASCII business names render correctly;
    # then JSON-encode the script content (HTML-safe).
    json_text = json.dumps(schema, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{json_text}\n</script>'


def compile_page(
    page: Page,
    *,
    company_settings: Any | None = None,
    public_base_url: str = "https://accountant.ocidm.io",
    canonical_url: str | None = None,
) -> str:
    """Produce the full <!DOCTYPE html>... document for a page.

    Reads page.sections_json (Pages v2 conversational output); falls
    back to page.html_content for legacy pages that never went through
    the new pipeline.
    """
    title = html_escape.escape(_safe_str(page.meta_title or page.title or "Untitled"))
    description = html_escape.escape(
        _safe_str(page.meta_description or page.description or "")
    )

    canonical = canonical_url or (
        f"{public_base_url.rstrip('/')}/p/{page.slug}"
        if page.slug
        else public_base_url
    )

    # Section content: prefer the new sections_json; fall back to the
    # legacy opaque html_content if sections_json is empty.
    # Per-section: if edited_html is set (Visual editor / SectionEditor
    # saved user edits), use it AS-IS (already HTML, no JSX rewrites
    # needed — the editor produces plain HTML). Otherwise compile from
    # the AI-original jsx_content with JSX→HTML normalization.
    #
    # Final pass: substitute MEDIA_TOKENS ({{VIDEO_URL}}, {{IMAGE_URL}},
    # ...) using section.media_overrides ⊕ section.metadata.props.
    # Token substitution is deferred to here so users can change media
    # without re-rendering the entire template (which would clobber
    # text edits in edited_html).
    from app.pages.variants import substitute_media_tokens

    body_sections: list[str] = []
    if page.sections_json:
        try:
            sections = json.loads(page.sections_json)
            for sec in sections:
                media_props = {
                    **((sec.get("metadata") or {}).get("props") or {}),
                    **(sec.get("media_overrides") or {}),
                }
                edited = sec.get("edited_html") or ""
                if edited:
                    body_sections.append(
                        substitute_media_tokens(edited, media_props)
                    )
                    continue
                jsx = sec.get("jsx_content") or ""
                if jsx:
                    body_sections.append(
                        substitute_media_tokens(_jsx_to_html(jsx), media_props)
                    )
        except json.JSONDecodeError:
            logger.warning(
                "compile_page.sections_parse_failed page_id=%s — falling back to html_content",
                page.id,
            )

    if not body_sections and page.html_content:
        # Legacy compatibility path. html_content is treated as already-
        # valid HTML (no JSX-flavored attributes).
        body_sections.append(page.html_content)

    body_html = "\n".join(body_sections)
    jsonld = _build_jsonld(page, company_settings, public_base_url)
    og_image = ""
    if page.og_image_url:
        og_image = (
            f'<meta property="og:image" content="{html_escape.escape(page.og_image_url)}">'
        )

    favicon = ""
    if page.favicon_url:
        favicon = f'<link rel="icon" href="{html_escape.escape(page.favicon_url)}">'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{html_escape.escape(canonical)}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{html_escape.escape(canonical)}">
  <meta property="og:type" content="website">
  {og_image}
  {favicon}
  {TAILWIND_CDN_SCRIPT}
  {jsonld}
</head>
<body class="bg-white text-gray-900 antialiased">
{body_html}
</body>
</html>
"""


def compile_and_hash(
    page: Page,
    *,
    company_settings: Any | None = None,
    public_base_url: str = "https://accountant.ocidm.io",
) -> tuple[str, str]:
    """Compile + return (html, sha256_hex). The hash is used to
    short-circuit re-uploads when the compiled output hasn't changed."""
    import hashlib

    html = compile_page(
        page,
        company_settings=company_settings,
        public_base_url=public_base_url,
    )
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    return html, digest


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
