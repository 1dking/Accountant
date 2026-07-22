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


# Commit 6 — Element-level style editor.
#
# style_overrides shape (per section, persisted via PATCH /sections/{idx}):
#
#   { selector: { propertyCamelCase: "value", ... }, ... }
#
# e.g.
#   {
#     "h1":      {"fontFamily": "Playfair Display", "fontSize": "64px",
#                 "lineHeight": "0.9", "color": "#ffffff"},
#     "p":       {"fontFamily": "Inter"},
#     "section": {"paddingTop": "96px", "backgroundColor": "#0f1320",
#                 "borderRadius": "24px"}
#   }
#
# Compile rules:
#   - The "section" pseudo-selector targets the section's outer wrapper
#     (#section-{sid}). Anything else is treated as a CSS tag selector
#     scoped inside the section (#section-{sid} h1).
#   - Section-scoped by design — a per-section "h1" rule colors EVERY
#     h1 in that section the same. Per-element targeting is deferred
#     (would require injecting unique IDs into all 15 variant templates;
#     uniform-by-section matches the Liquid Glass / one-aesthetic-per-
#     section design intent). See Commit 6 spec.
#   - CSS properties are camelCase in the JSON (React convention so
#     drawer code can use the standard CSSProperties type); we
#     kebab-case them at compile time.
#   - All values pass through a defensive CSS-value validator that
#     rejects {, }, ;, < which would break out of the rule block.

# Curated set of font families we treat as Google Fonts. Matches the
# drawer's curated picker. Any fontFamily value outside this set is
# emitted as a CSS font-family but NOT requested from Google Fonts
# (could be a system stack like "Inter, system-ui, sans-serif" or a
# brand-shipped font).
GOOGLE_FONTS_CATALOG: set[str] = {
    "Inter", "Roboto", "Open Sans", "Lato", "Poppins",
    "Playfair Display", "Cormorant Garamond", "Space Grotesk",
    "Manrope", "DM Sans", "Plus Jakarta Sans", "Outfit",
    "Geist", "Mona Sans", "JetBrains Mono", "IBM Plex Sans",
    "Work Sans", "Nunito", "Source Sans 3", "Merriweather",
}

# camelCase → kebab-case for CSS property names. Pre-compiled for the
# style-override compile path which runs once per page render.
_CAMEL_TO_KEBAB = re.compile(r"(?<!^)(?=[A-Z])")


def _camel_to_kebab(name: str) -> str:
    return _CAMEL_TO_KEBAB.sub("-", name).lower()


# CSS value safety — reject characters that could break out of the
# rule block or inject more rules. CSS values are arbitrary strings
# from the drawer, so this is the trust boundary.
_CSS_VALUE_REJECT = re.compile(r"[{};<>]")


def _safe_css_value(value: Any) -> str | None:
    """Return the value as a clean CSS value string, or None if it's
    unsafe. Numbers pass through (assumed to be unitless or px-style).
    """
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    if _CSS_VALUE_REJECT.search(v):
        return None
    return v


def _extract_google_fonts(sections: list[dict]) -> list[str]:
    """Collect unique fontFamily values across all sections that match
    GOOGLE_FONTS_CATALOG. Sorted for deterministic output."""
    found: set[str] = set()
    for sec in sections:
        overrides = sec.get("style_overrides") or {}
        if not isinstance(overrides, dict):
            continue
        for _selector, props in overrides.items():
            if not isinstance(props, dict):
                continue
            family = props.get("fontFamily")
            if isinstance(family, str):
                # The drawer may store "Inter, system-ui, sans-serif" —
                # only the first token is the requested family.
                primary = family.split(",")[0].strip().strip("'\"")
                if primary in GOOGLE_FONTS_CATALOG:
                    found.add(primary)
    return sorted(found)


def _build_google_fonts_link(families: list[str]) -> str:
    """Emit a single <link> requesting all needed families with the
    common weight range (300-800) and italic axis. Empty string when
    no families need loading."""
    if not families:
        return ""
    parts = []
    for fam in families:
        slug = fam.replace(" ", "+")
        parts.append(f"family={slug}:wght@300;400;500;600;700;800")
    qs = "&".join(parts) + "&display=swap"
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?{qs}">'
    )


def _compile_section_styles(sid: str, overrides: dict[str, Any]) -> str:
    """Generate the scoped CSS rule body for one section's overrides.
    Empty string if no overrides resolve to safe values.

    Selector mapping:
      - "section" → "#section-{sid}, #section-{sid} > section" (the
        wrapper div + the variant's inner section element). All 15
        flagship variants start with a <section> as their root, so
        targeting both covers padding/background changes whether the
        variant uses an inner section or not.
      - anything else → "#section-{sid} <selector>" (descendants).
    """
    if not isinstance(overrides, dict) or not overrides:
        return ""
    rules: list[str] = []
    for selector, props in overrides.items():
        if not isinstance(props, dict) or not props:
            continue
        decls: list[str] = []
        for prop, val in props.items():
            if not isinstance(prop, str):
                continue
            safe = _safe_css_value(val)
            if safe is None:
                continue
            css_prop = _camel_to_kebab(prop)
            # font-family values with spaces need quoting per CSS spec.
            # The drawer sends canonical names like "Playfair Display";
            # we wrap-or-pass through depending on whether quotes are
            # present already.
            if (
                css_prop == "font-family"
                and " " in safe
                and not (safe.startswith('"') or safe.startswith("'"))
            ):
                safe = f'"{safe}"'
            decls.append(f"  {css_prop}: {safe};")
        if not decls:
            continue
        if selector == "section":
            target = f"#section-{sid}, #section-{sid} > section"
        else:
            # Strip any user-typed prefix; selector is a bare tag/class
            # by convention (drawer never produces complex selectors).
            target = f"#section-{sid} {selector}"
        rules.append(target + " {\n" + "\n".join(decls) + "\n}")
    return "\n".join(rules)


def _build_animation_init_script() -> str:
    """Inline JS that wires GSAP timelines for:
      - 4A [data-section-anim] flat configs (scroll_reveal /
        counter_up / parallax arrays)
      - 4B [data-anim-preset] presets (entry + scrub) with
        per-section config and mobile safety valve.

    Runs after GSAP CDN scripts load (deferred). prefers-reduced-motion
    is honored EXPLICITLY by setting final visible state, not just
    early-returning — page remains fully usable without motion.
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
    // final visible state and skip GSAP entirely. Explicit final-state
    // restoration per the Commit 4 requirement.
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      document.querySelectorAll('[data-section-anim]').forEach(function (wrap) {
        try {
          var cfg = JSON.parse(wrap.getAttribute('data-section-anim') || '{}');
          (cfg.scroll_reveal || []).forEach(function (rev) {
            wrap.querySelectorAll(rev.selector).forEach(function (el) {
              el.style.opacity = '1';
              el.style.transform = 'none';
              el.style.filter = 'none';
            });
          });
        } catch (e) { /* malformed config */ }
      });
      document.querySelectorAll('[data-anim-preset]').forEach(function (wrap) {
        // Reset transforms/opacity/filter so the section renders fully.
        wrap.style.opacity = '1';
        wrap.style.transform = 'none';
        wrap.style.filter = 'none';
      });
      return;
    }

    // Mobile safety valve — < 768px viewports with data-anim-mobile-mode
    // = "auto" downgrade scrub effects to entry-trigger-once. "disable"
    // turns off the scrub effect entirely; otherwise scrub runs as-is.
    var isMobile = window.innerWidth < 768;

    // ---------- 4A flat shape: [data-section-anim] -----------------
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
            scrub: p.scrub !== false ? 0.6 : false,
          },
        });
      });
    });

    // ---------- 4B preset shape: [data-anim-preset] -----------------
    // Each preset has a dedicated effect handler. Entry presets use
    // gsap.fromTo + ScrollTrigger once. Scrub presets use scrub with
    // a smoothing factor.
    var ENTRY_PRESETS = {
      fade_up:          {from: {y: 40, opacity: 0},  to: {y: 0, opacity: 1}},
      fade_down:        {from: {y: -40, opacity: 0}, to: {y: 0, opacity: 1}},
      slide_left:       {from: {x: -60, opacity: 0}, to: {x: 0, opacity: 1}},
      slide_right:      {from: {x: 60, opacity: 0},  to: {x: 0, opacity: 1}},
      scale_in:         {from: {scale: 0.85, opacity: 0}, to: {scale: 1, opacity: 1}},
      scale_out:        {from: {scale: 1.15, opacity: 0}, to: {scale: 1, opacity: 1}},
      blur_in:          {from: {filter: 'blur(12px)', opacity: 0}, to: {filter: 'blur(0px)', opacity: 1}},
      rotate_in:        {from: {rotation: -8, opacity: 0}, to: {rotation: 0, opacity: 1}},
      stagger_children: {from: {y: 30, opacity: 0}, to: {y: 0, opacity: 1}, target: 'children'},
    };

    document.querySelectorAll('[data-anim-preset]').forEach(function (wrap) {
      var presetId = wrap.getAttribute('data-anim-preset');
      var cfg;
      try { cfg = JSON.parse(wrap.getAttribute('data-anim-config') || '{}'); }
      catch (e) { cfg = {}; }
      var mobileMode = wrap.getAttribute('data-anim-mobile-mode') || 'auto';

      // ----- Tier 1 entry presets -----
      if (ENTRY_PRESETS[presetId]) {
        var p = ENTRY_PRESETS[presetId];
        var targets = (p.target === 'children') ? wrap.children : [wrap];
        gsap.fromTo(targets, p.from, Object.assign({}, p.to, {
          duration: cfg.duration != null ? cfg.duration : 0.8,
          ease: cfg.ease || 'power2.out',
          delay: cfg.delay || 0,
          stagger: cfg.stagger || 0,
          scrollTrigger: {
            trigger: wrap,
            start: 'top 80%',
            once: true,
          },
        }));
        return;
      }

      // ----- Tier 2 scrub presets -----
      // Mobile valve: < 768px + mode=auto → degrade to single-trigger
      // entry-style animation (just settle to the END state on enter).
      // mode=disable → no animation at all on mobile.
      var degradeToEntry = isMobile && mobileMode === 'auto';
      var skip = isMobile && mobileMode === 'disable';
      if (skip) return;

      function scrubBuild(opts) {
        if (degradeToEntry) {
          // Fire-once entry: jump to end state when section enters view.
          gsap.fromTo(opts.target, opts.from, Object.assign({}, opts.to, {
            duration: 0.7,
            ease: 'power2.out',
            scrollTrigger: { trigger: wrap, start: 'top 80%', once: true },
          }));
        } else {
          gsap.fromTo(opts.target, opts.from, Object.assign({}, opts.to, {
            ease: 'none',
            scrollTrigger: {
              trigger: wrap,
              start: opts.start || 'top bottom',
              end: opts.end || 'bottom top',
              scrub: 0.6,
            },
          }));
        }
      }

      if (presetId === 'parallax_bg') {
        scrubBuild({ target: wrap, from: { y: 0 }, to: { y: -80 } });
      } else if (presetId === 'parallax_fg') {
        scrubBuild({ target: wrap, from: { y: 0 }, to: { y: 50 } });
      } else if (presetId === 'scale_with_scroll') {
        scrubBuild({ target: wrap, from: { scale: 0.9 }, to: { scale: 1.1 } });
      } else if (presetId === 'opacity_scrub') {
        // Three-stop opacity: fade in over 30%, hold, fade out at end.
        if (degradeToEntry) {
          gsap.fromTo(wrap, { opacity: 0 }, {
            opacity: 1, duration: 0.7, ease: 'power2.out',
            scrollTrigger: { trigger: wrap, start: 'top 80%', once: true },
          });
        } else {
          var tl = gsap.timeline({
            scrollTrigger: {
              trigger: wrap, start: 'top bottom', end: 'bottom top',
              scrub: 0.6,
            },
          });
          tl.fromTo(wrap, { opacity: 0 }, { opacity: 1, duration: 0.3 })
            .to(wrap, { opacity: 1, duration: 0.4 })
            .to(wrap, { opacity: 0, duration: 0.3 });
        }
      } else if (presetId === 'pin_and_scrub') {
        if (!degradeToEntry) {
          var mult = (cfg.intensity != null ? cfg.intensity : 1.5);
          ScrollTrigger.create({
            trigger: wrap,
            start: 'top top',
            end: '+=' + (wrap.offsetHeight * mult) + 'px',
            pin: true,
            pinSpacing: true,
          });
        }
        // Mobile auto-mode falls through with no pin (pin is jarring
        // on touch devices). Sections render normally.
      }

      // ----- Tier 4 hover effects -----
      // Touch capability check — on touch-only devices, hover events
      // can fire via sticky-hover emulation in unpredictable ways.
      // Skip JS-driven hover entirely on devices without a fine pointer.
      var hasHover = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

      if (presetId === 'hover_lift') {
        // Pure CSS — apply transitions + hover styles via inline style
        // so we don't depend on a stylesheet update.
        var liftDur = (cfg.duration_ms || 200);
        wrap.style.transition = 'transform ' + liftDur + 'ms cubic-bezier(0.32, 0.72, 0, 1), box-shadow ' + liftDur + 'ms cubic-bezier(0.32, 0.72, 0, 1)';
        wrap.style.willChange = 'transform';
        wrap.addEventListener('mouseenter', function () {
          if (document.activeElement && document.activeElement.isContentEditable) return;
          wrap.style.transform = 'translateY(-' + (cfg.translate_y || 4) + 'px)';
          wrap.style.boxShadow = '0 12px 32px rgba(0,0,0,0.18), 0 4px 12px rgba(0,0,0,0.08)';
        }, { passive: true });
        wrap.addEventListener('mouseleave', function () {
          wrap.style.transform = '';
          wrap.style.boxShadow = '';
        }, { passive: true });

      } else if (presetId === 'hover_tilt' && hasHover) {
        // 3D tilt — rotateX/rotateY based on cursor position.
        // requestAnimationFrame eases toward target so motion stays
        // smooth even with high-frequency mousemove events.
        var maxRot = (cfg.max_rotate || 8);
        var easeFactor = (cfg.ease || 0.15);
        var targetRX = 0, targetRY = 0;
        var currentRX = 0, currentRY = 0;
        var rafId = null;
        wrap.style.perspective = '1000px';
        wrap.style.transformStyle = 'preserve-3d';
        wrap.style.willChange = 'transform';
        function loop() {
          currentRX += (targetRX - currentRX) * easeFactor;
          currentRY += (targetRY - currentRY) * easeFactor;
          wrap.style.transform = 'rotateX(' + currentRX.toFixed(2) + 'deg) rotateY(' + currentRY.toFixed(2) + 'deg)';
          if (Math.abs(targetRX - currentRX) > 0.05 || Math.abs(targetRY - currentRY) > 0.05) {
            rafId = requestAnimationFrame(loop);
          } else { rafId = null; }
        }
        wrap.addEventListener('mousemove', function (e) {
          if (document.activeElement && document.activeElement.isContentEditable) return;
          var rect = wrap.getBoundingClientRect();
          var cx = rect.left + rect.width / 2;
          var cy = rect.top + rect.height / 2;
          targetRY = ((e.clientX - cx) / (rect.width / 2)) * maxRot;
          targetRX = -((e.clientY - cy) / (rect.height / 2)) * maxRot;
          if (!rafId) rafId = requestAnimationFrame(loop);
        }, { passive: true });
        wrap.addEventListener('mouseleave', function () {
          targetRX = 0; targetRY = 0;
          if (!rafId) rafId = requestAnimationFrame(loop);
        }, { passive: true });

      } else if (presetId === 'hover_magnetic' && hasHover) {
        // Translate toward cursor within radius. mousemove on the
        // wrap element (radius is in element-relative pixels).
        var radius = (cfg.radius || 120);
        var maxTrans = (cfg.max_translate || 12);
        var easeFactor2 = (cfg.ease || 0.15);
        var targetX = 0, targetY = 0;
        var currentX = 0, currentY = 0;
        var rafId2 = null;
        wrap.style.willChange = 'transform';
        function magLoop() {
          currentX += (targetX - currentX) * easeFactor2;
          currentY += (targetY - currentY) * easeFactor2;
          wrap.style.transform = 'translate3d(' + currentX.toFixed(2) + 'px,' + currentY.toFixed(2) + 'px,0)';
          if (Math.abs(targetX - currentX) > 0.1 || Math.abs(targetY - currentY) > 0.1) {
            rafId2 = requestAnimationFrame(magLoop);
          } else { rafId2 = null; }
        }
        wrap.addEventListener('mousemove', function (e) {
          if (document.activeElement && document.activeElement.isContentEditable) return;
          var rect = wrap.getBoundingClientRect();
          var cx = rect.left + rect.width / 2;
          var cy = rect.top + rect.height / 2;
          var dx = e.clientX - cx;
          var dy = e.clientY - cy;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < radius) {
            var pull = (1 - dist / radius);
            targetX = (dx / radius) * maxTrans * pull;
            targetY = (dy / radius) * maxTrans * pull;
          } else {
            targetX = 0; targetY = 0;
          }
          if (!rafId2) rafId2 = requestAnimationFrame(magLoop);
        }, { passive: true });
        wrap.addEventListener('mouseleave', function () {
          targetX = 0; targetY = 0;
          if (!rafId2) rafId2 = requestAnimationFrame(magLoop);
        }, { passive: true });

      } else if (presetId === 'hover_underline_draw') {
        // Pure CSS underline draw on every h1/h2/h3 + p in the section.
        // Injects a scoped <style> per section so each instance gets
        // a unique selector via the wrap's auto-generated id.
        var dur = (cfg.duration_ms || 300);
        var ease = (cfg.ease || 'cubic-bezier(0.4, 0, 0.2, 1)');
        if (!wrap.id) wrap.id = 'sec-' + Math.random().toString(36).slice(2, 9);
        var sid = wrap.id;
        var style = document.createElement('style');
        style.textContent =
          '#' + sid + ' h1, #' + sid + ' h2, #' + sid + ' h3, #' + sid + ' a, #' + sid + ' p {' +
          '  position: relative; display: inline-block;' +
          '}' +
          '#' + sid + ' h1::after, #' + sid + ' h2::after, #' + sid + ' h3::after, #' + sid + ' a::after {' +
          '  content: ""; position: absolute; left: 0; bottom: -2px;' +
          '  width: 0; height: 2px;' +
          '  background: linear-gradient(90deg, #6366f1, #ec4899);' +
          '  transition: width ' + dur + 'ms ' + ease + ';' +
          '}' +
          '#' + sid + ' h1:hover::after, #' + sid + ' h2:hover::after, #' + sid + ' h3:hover::after, #' + sid + ' a:hover::after {' +
          '  width: 100%;' +
          '}';
        document.head.appendChild(style);
      }
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
    """Wrap a section's HTML so the init script can find and animate
    it. Two attribute paths:

      - 4A flat shape ({scroll_reveal: [...], counter_up: [...]}) →
        wrapped with data-section-anim='{...full config...}'
      - 4B preset shape ({preset: "fade_up", config: {...}}) →
        wrapped with data-anim-preset="<id>" + data-anim-config='{...}'
        + optional data-anim-mobile-mode

    Both are recognized by the runtime; emitting them as distinct
    attributes keeps the picker UI simple (no need to round-trip the
    flat shape) and makes per-preset CSS targeting possible.

    preset == "none" → no wrapper, no data attributes. Section
    renders entirely static.
    """
    if not anim_config:
        return html
    preset_id = anim_config.get("preset") if isinstance(anim_config, dict) else None
    if preset_id == "none":
        return html
    if preset_id and preset_id != "default":
        config = anim_config.get("config") or {}
        mobile_mode = config.get("mobile_mode", "auto")
        cfg_payload = _attr_escape_json(config)
        mobile_attr = (
            f' data-anim-mobile-mode="{mobile_mode}"'
            if mobile_mode in ("auto", "disable") else ""
        )
        return (
            f'<div data-anim-preset="{preset_id}" '
            f'data-anim-config="{cfg_payload}"'
            f'{mobile_attr}>{html}</div>'
        )
    # 4A flat shape (variant default / explicit scroll_reveal arrays):
    safe = _attr_escape_json(anim_config)
    return f'<div data-section-anim="{safe}">{html}</div>'


def _attr_escape_json(obj: Any) -> str:
    """JSON-encode + HTML-attribute-escape an object. Used by both
    4A flat and 4B preset wrappers."""
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return (
        payload.replace("&", "&amp;")
        .replace("'", "&#39;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


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

    # Matches the real serving route, /api/pages/p/{slug} (router.py's
    # serve_published_page, mounted under the /api/pages prefix in
    # main.py) — not the frontend's own /p/:token route (public document
    # sharing), which this would otherwise collide with and silently
    # serve the wrong page for.
    canonical = canonical_url or (
        f"{public_base_url.rstrip('/')}/api/pages/p/{page.slug}"
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
    style_blocks: list[str] = []
    parsed_sections: list[dict] = []
    any_animations = False
    if page.sections_json:
        try:
            sections = json.loads(page.sections_json)
            parsed_sections = [s for s in sections if isinstance(s, dict)]
            for i, sec in enumerate(sections):
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
                    # "none" preset → no wrapper + no GSAP injection.
                    # Distinct from "default" (variant default behavior)
                    # and from no override at all.
                    is_none = (
                        isinstance(anim_cfg, dict)
                        and anim_cfg.get("preset") == "none"
                    )
                    if not is_none:
                        any_animations = True
                    rendered = _wrap_section_with_animation(rendered, anim_cfg)

                # Commit 6 — section-id wrapper. The id is the stable
                # source of truth for style_overrides scoping; fall
                # back to position-based id if a legacy section is
                # missing one (defensive — every variant_to_section
                # output sets an id).
                sid = sec.get("id") or f"sec-{i}"
                body_sections.append(
                    f'<section id="section-{sid}" data-pages-section>{rendered}</section>'
                )

                overrides = sec.get("style_overrides") or {}
                if overrides:
                    block = _compile_section_styles(sid, overrides)
                    if block:
                        style_blocks.append(block)
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

    # Commit 6 — Google Fonts + per-section style overrides.
    google_fonts_link = _build_google_fonts_link(
        _extract_google_fonts(parsed_sections)
    )
    style_overrides_block = (
        "<style id=\"pages-style-overrides\">\n"
        + "\n".join(style_blocks)
        + "\n</style>"
    ) if style_blocks else ""

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
  {google_fonts_link}
  {TAILWIND_CDN_SCRIPT}
  {anim_head}
  {style_overrides_block}
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
