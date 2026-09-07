"""CSS-only motion presets (block model v2, tier "css").

Scroll-driven animations via `animation-timeline: view()/scroll()` — no
GSAP, no runtime JS. Browsers without support (≈16 % in 2026) simply see
the resting state: every preset is written so the un-animated element is
fully visible, and the S2 runtime adds an IntersectionObserver fallback.
`prefers-reduced-motion` disables all of them.

A block declares `SectionVariant.motion_preset`; `variant_to_section`
copies it into `section.metadata.motion_preset`; `compile_page` emits
`data-motion="<id>"` on the section wrapper and includes the CSS for
the presets actually used on the page (once, in <head>).
"""
from __future__ import annotations

# id → {label, label_fr, css}. Selectors are scoped to [data-motion=id].
CSS_MOTION_PRESETS: dict[str, dict[str, str]] = {
    "css_reveal_up": {
        "label": "Reveal up",
        "label_fr": "Apparition vers le haut",
        "css": """
[data-motion="css_reveal_up"] > * { animation: pg-reveal-up both linear; animation-timeline: view(); animation-range: entry 0% entry 40%; }
@keyframes pg-reveal-up { from { opacity: 0; transform: translateY(32px); } to { opacity: 1; transform: none; } }
""",
    },
    "css_reveal_fade": {
        "label": "Fade in",
        "label_fr": "Fondu",
        "css": """
[data-motion="css_reveal_fade"] > * { animation: pg-reveal-fade both linear; animation-timeline: view(); animation-range: entry 0% entry 35%; }
@keyframes pg-reveal-fade { from { opacity: 0; } to { opacity: 1; } }
""",
    },
    "css_scale_on_scroll": {
        "label": "Scale in",
        "label_fr": "Zoom à l’arrivée",
        "css": """
[data-motion="css_scale_on_scroll"] > * { animation: pg-scale-in both ease-out; animation-timeline: view(); animation-range: entry 0% entry 50%; transform-origin: center bottom; }
@keyframes pg-scale-in { from { opacity: 0; transform: scale(.92); } to { opacity: 1; transform: none; } }
""",
    },
    "css_parallax_slow": {
        "label": "Parallax background",
        "label_fr": "Parallaxe d’arrière-plan",
        "css": """
[data-motion="css_parallax_slow"] { overflow: hidden; }
[data-motion="css_parallax_slow"] [data-parallax], [data-motion="css_parallax_slow"] > * > .absolute.inset-0 { animation: pg-parallax both linear; animation-timeline: view(); animation-range: cover 0% cover 100%; will-change: transform; }
@keyframes pg-parallax { from { transform: translateY(-12%); } to { transform: translateY(12%); } }
""",
    },
    "css_kinetic_headline": {
        "label": "Kinetic headline",
        "label_fr": "Titre cinétique",
        "css": """
[data-motion="css_kinetic_headline"] h1, [data-motion="css_kinetic_headline"] h2 { animation: pg-kinetic both cubic-bezier(.2,.7,.2,1); animation-timeline: view(); animation-range: entry 0% entry 60%; }
@keyframes pg-kinetic { from { opacity: 0; letter-spacing: .12em; transform: translateY(24px) skewY(2deg); } to { opacity: 1; letter-spacing: normal; transform: none; } }
""",
    },
    "css_marquee": {
        "label": "Marquee",
        "label_fr": "Défilement continu",
        "css": """
[data-motion="css_marquee"] [data-marquee] { display: flex; gap: 3rem; width: max-content; animation: pg-marquee 28s linear infinite; }
[data-motion="css_marquee"]:hover [data-marquee] { animation-play-state: paused; }
@keyframes pg-marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
""",
    },
    "css_progress_bar": {
        "label": "Scroll progress bar",
        "label_fr": "Barre de progression",
        "css": """
[data-motion="css_progress_bar"] [data-progress] { position: fixed; top: 0; left: 0; height: 3px; width: 100%; transform-origin: 0 50%; animation: pg-progress linear both; animation-timeline: scroll(root); z-index: 60; }
@keyframes pg-progress { from { transform: scaleX(0); } to { transform: scaleX(1); } }
""",
    },
}

MOTION_PRESET_IDS: frozenset[str] = frozenset(CSS_MOTION_PRESETS)

_BASE = """
@media (prefers-reduced-motion: reduce) { [data-motion] *, [data-motion] { animation: none !important; } }
"""


def is_valid_motion_preset(preset_id: str | None) -> bool:
    return bool(preset_id) and preset_id in CSS_MOTION_PRESETS


def build_motion_css(preset_ids: set[str] | list[str]) -> str:
    """One <style> block with the CSS for the presets in use. Marquee is
    a plain keyframe animation (works everywhere); the scroll-driven
    presets sit behind @supports so unsupported browsers keep the
    resting, fully visible state."""
    used = [p for p in CSS_MOTION_PRESETS if p in set(preset_ids)]
    if not used:
        return ""
    plain = [CSS_MOTION_PRESETS[p]["css"].strip() for p in used if p == "css_marquee"]
    scroll = [CSS_MOTION_PRESETS[p]["css"].strip() for p in used if p != "css_marquee"]
    parts = ['<style id="pages-motion">', _BASE.strip()]
    parts.extend(plain)
    if scroll:
        parts.append("@supports (animation-timeline: view()) {")
        parts.extend(scroll)
        parts.append("}")
    parts.append("</style>")
    return "\n".join(parts)


def list_motion_presets(locale: str = "en") -> list[dict]:
    return [
        {"id": pid, "label": (p["label_fr"] if locale.startswith("fr") else p["label"])}
        for pid, p in CSS_MOTION_PRESETS.items()
    ]
