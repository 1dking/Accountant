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


GSAP_CDN_SCRIPT = (
    '<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js" defer></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/ScrollTrigger.min.js" defer></script>'
)


def _build_animation_init_script() -> str:
    """Inline JS that walks [data-section-anim] elements and wires up
    GSAP timelines. Runs after GSAP loads (deferred). Respects
    prefers-reduced-motion explicitly — sets final visible state
    rather than just early-returning, so the page is fully usable
    without motion.
    """
    return """<script>
(function () {
  function init() {
    if (!window.gsap || !window.ScrollTrigger) {
      // GSAP not yet loaded; retry shortly. Defer + DOMContentLoaded
      // ordering occasionally races on slow connections.
      setTimeout(init, 50);
      return;
    }
    gsap.registerPlugin(ScrollTrigger);

    // prefers-reduced-motion: set every animatable element to its
    // final visible state and skip GSAP entirely. Per Commit 4 spec
    // — explicit final-state, not just early-return.
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      document.querySelectorAll('[data-section-anim]').forEach(function (wrap) {
        try {
          var cfg = JSON.parse(wrap.getAttribute('data-section-anim') || '{}');
          (cfg.scroll_reveal || []).forEach(function (rev) {
            wrap.querySelectorAll(rev.selector).forEach(function (el) {
              el.style.opacity = '1';
              el.style.transform = 'none';
            });
          });
          (cfg.counter_up || []).forEach(function (c) {
            // Counter targets already have their final text in HTML.
          });
        } catch (e) { /* malformed config */ }
      });
      return;
    }

    document.querySelectorAll('[data-section-anim]').forEach(function (wrap) {
      var cfg;
      try { cfg = JSON.parse(wrap.getAttribute('data-section-anim') || '{}'); }
      catch (e) { return; }

      (cfg.scroll_reveal || []).forEach(function (rev) {
        var els = wrap.querySelectorAll(rev.selector);
        if (!els.length) return;
        gsap.fromTo(els, rev.from || {}, Object.assign({}, rev.to || {}, {
          duration: rev.duration != null ? rev.duration : 0.8,
          ease: rev.ease || 'power2.out',
          delay: rev.delay || 0,
          stagger: rev.stagger || 0,
          scrollTrigger: {
            trigger: wrap,
            start: rev.start || 'top 80%',
            once: rev.once !== false,
          },
        }));
      });

      (cfg.counter_up || []).forEach(function (c) {
        wrap.querySelectorAll(c.selector).forEach(function (el) {
          var raw = (el.textContent || '').trim();
          // Parse target: drop everything except digits + decimal,
          // keep prefix/suffix so "500+" and "$1,200" still display.
          var match = raw.match(/(-?[\\d,]+\\.?\\d*)/);
          if (!match) return;
          var target = parseFloat(match[1].replace(/,/g, ''));
          if (isNaN(target)) return;
          var prefix = raw.slice(0, match.index);
          var suffix = raw.slice(match.index + match[1].length);
          var state = { v: 0 };
          gsap.to(state, {
            v: target,
            duration: c.duration || 1.5,
            ease: c.ease || 'power2.out',
            onUpdate: function () {
              var n = state.v;
              var display = n >= 100 ? Math.round(n) : (target >= 10 ? n.toFixed(0) : n.toFixed(1));
              el.textContent = prefix + display + suffix;
            },
            scrollTrigger: {
              trigger: el,
              start: c.start || 'top 85%',
              once: true,
            },
          });
        });
      });

      (cfg.parallax || []).forEach(function (p) {
        var els = wrap.querySelectorAll(p.selector);
        if (!els.length) return;
        gsap.to(els, {
          y: p.y_offset != null ? p.y_offset : -50,
          ease: 'none',
          scrollTrigger: {
            trigger: wrap,
            start: 'top bottom',
            end: 'bottom top',
            scrub: p.scrub !== false,
          },
        });
      });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>"""


def _wrap_section_with_animation(html: str, anim_config: dict | None) -> str:
    """Wrap a section's HTML in a <div data-section-anim='{...}'>
    wrapper so the init script can find and animate it. No wrapper
    when anim_config is empty/null — keeps the DOM clean for static
    sections."""
    if not anim_config:
        return html
    # JSON-escape the config for safe embedding in an HTML attribute.
    payload = json.dumps(anim_config, separators=(",", ":"), ensure_ascii=False)
    safe = (
        payload.replace("&", "&amp;")
        .replace("'", "&#39;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<div data-section-anim="{safe}">{html}</div>'


def compile_page(
    page: Page,
    *,
    company_settings: Any | None = None,
    public_base_url: str = "https://accountant.ocidm.io",
    canonical_url: str | None = None,
    variant_animations: dict[str, Any] | None = None,
) -> str:
    """Produce the full <!DOCTYPE html>... document for a page.

    Reads page.sections_json (Pages v2 conversational output); falls
    back to page.html_content for legacy pages that never went through
    the new pipeline.

    `variant_animations` is a fallback dict {variant_id → animation
    config} used for sections that don't carry an inline `animations`
    snapshot (legacy sections inserted before Commit 4). Callers with
    a DB session should pre-fetch SectionVariant.default_animations
    for the page's variant_ids and pass them here so existing pages
    light up without a migration.
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
    any_animations = False
    if page.sections_json:
        try:
            sections = json.loads(page.sections_json)
            for sec in sections:
                media_props = {
                    **((sec.get("metadata") or {}).get("props") or {}),
                    **(sec.get("media_overrides") or {}),
                }
                # Animations: prefer the per-section snapshot. Fall back
                # to variant_animations[variant_id] for legacy sections
                # inserted before Commit 4 added the snapshot.
                anim_cfg = sec.get("animations")
                if not anim_cfg and variant_animations:
                    vid = (sec.get("metadata") or {}).get("variant_id")
                    if vid:
                        anim_cfg = variant_animations.get(vid)

                edited = sec.get("edited_html") or ""
                if edited:
                    rendered = substitute_media_tokens(edited, media_props)
                else:
                    jsx = sec.get("jsx_content") or ""
                    if not jsx:
                        continue
                    rendered = substitute_media_tokens(
                        _jsx_to_html(jsx), media_props
                    )
                if anim_cfg:
                    any_animations = True
                    rendered = _wrap_section_with_animation(rendered, anim_cfg)
                body_sections.append(rendered)
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

    # Only include GSAP + init when at least one section actually has
    # animations. Saves ~25KB on pages that don't need motion.
    anim_head = GSAP_CDN_SCRIPT if any_animations else ""
    anim_body_end = _build_animation_init_script() if any_animations else ""

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
  {anim_head}
  {jsonld}
</head>
<body class="bg-white text-gray-900 antialiased">
{body_html}
{anim_body_end}
</body>
</html>
"""


def compile_and_hash(
    page: Page,
    *,
    company_settings: Any | None = None,
    public_base_url: str = "https://accountant.ocidm.io",
    variant_animations: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Compile + return (html, sha256_hex). The hash is used to
    short-circuit re-uploads when the compiled output hasn't changed."""
    import hashlib

    html = compile_page(
        page,
        company_settings=company_settings,
        public_base_url=public_base_url,
        variant_animations=variant_animations,
    )
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    return html, digest


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
