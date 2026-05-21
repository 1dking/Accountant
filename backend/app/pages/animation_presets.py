"""Animation preset registry — Commit 4B.

14 named presets across 2 tiers:
  Tier 1 (entry):  fade_up, fade_down, slide_left, slide_right,
                   scale_in, scale_out, blur_in, rotate_in,
                   stagger_children
  Tier 2 (scroll-driven, scrub):
                   parallax_bg, parallax_fg, scale_with_scroll,
                   opacity_scrub, pin_and_scrub

Tier 4 hover effects (hover_lift/tilt/magnetic/underline_draw) ship
in 4B.2 follow-up.

Each preset has:
  - id            — string key used in section.animations.preset
  - tier          — "entry" | "scrub"
  - display_name  — picker card label
  - description   — 1-line tooltip
  - defaults      — config defaults the user sees in the picker
                    config panel (duration / delay / ease / stagger)
  - gsap_config   — the GSAP timeline shape the init script reads.
                    Includes a `_kind` tag the runtime uses to route
                    to the right helper (entry vs scrub).

The compile step injects a per-section data-anim-preset="ID"
attribute, and the init script reads PRESET_RUNTIME (mirrored client
side from this file) to wire the right effect.
"""
from __future__ import annotations

# Each tier1 entry preset specifies a GSAP fromTo. The init script
# wraps these in a ScrollTrigger with start:'top 80%', once:true.
TIER1_ENTRY: dict[str, dict] = {
    "fade_up": {
        "tier": "entry",
        "display_name": "Fade up",
        "description": "Element drifts up from below as it enters view.",
        "defaults": {"duration": 0.8, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"y": 40, "opacity": 0},
        "to": {"y": 0, "opacity": 1},
    },
    "fade_down": {
        "tier": "entry",
        "display_name": "Fade down",
        "description": "Element settles down from above.",
        "defaults": {"duration": 0.8, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"y": -40, "opacity": 0},
        "to": {"y": 0, "opacity": 1},
    },
    "slide_left": {
        "tier": "entry",
        "display_name": "Slide in from left",
        "description": "Element slides in from the left edge.",
        "defaults": {"duration": 0.9, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"x": -60, "opacity": 0},
        "to": {"x": 0, "opacity": 1},
    },
    "slide_right": {
        "tier": "entry",
        "display_name": "Slide in from right",
        "description": "Element slides in from the right edge.",
        "defaults": {"duration": 0.9, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"x": 60, "opacity": 0},
        "to": {"x": 0, "opacity": 1},
    },
    "scale_in": {
        "tier": "entry",
        "display_name": "Scale in",
        "description": "Element grows from 85% to full size.",
        "defaults": {"duration": 0.7, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"scale": 0.85, "opacity": 0},
        "to": {"scale": 1, "opacity": 1},
    },
    "scale_out": {
        "tier": "entry",
        "display_name": "Scale out",
        "description": "Element shrinks from 115% to full size.",
        "defaults": {"duration": 0.7, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"scale": 1.15, "opacity": 0},
        "to": {"scale": 1, "opacity": 1},
    },
    "blur_in": {
        "tier": "entry",
        "display_name": "Blur in",
        "description": "Element resolves from a soft blur to sharp.",
        "defaults": {"duration": 0.9, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"filter": "blur(12px)", "opacity": 0},
        "to": {"filter": "blur(0px)", "opacity": 1},
    },
    "rotate_in": {
        "tier": "entry",
        "display_name": "Rotate in",
        "description": "Element rotates slightly into place.",
        "defaults": {"duration": 0.9, "delay": 0, "ease": "power2.out", "stagger": 0},
        "from": {"rotation": -8, "opacity": 0},
        "to": {"rotation": 0, "opacity": 1},
    },
    "stagger_children": {
        "tier": "entry",
        "display_name": "Stagger children",
        "description": "Direct children fade up one after another.",
        "defaults": {"duration": 0.6, "delay": 0, "ease": "power2.out", "stagger": 0.1},
        # Stagger applies to the section's direct children — runtime
        # picks them via `:scope > *` from the wrapper element.
        "from": {"y": 30, "opacity": 0},
        "to": {"y": 0, "opacity": 1},
        "target": "children",
    },
}


# Tier 2 scrub effects — continuous as user scrolls past the section.
# Each has a y_from/y_to delta or scale/opacity range applied via
# ScrollTrigger.scrub. The mobile safety valve degrades these to
# fire-once entry triggers on < 768px viewports when mobile_mode=auto.
TIER2_SCRUB: dict[str, dict] = {
    "parallax_bg": {
        "tier": "scrub",
        "display_name": "Parallax background",
        "description": "Section drifts slowly opposite to scroll. Adds depth.",
        "defaults": {"intensity": 0.3, "mobile_mode": "auto"},
        "scrub": {"y_from": 0, "y_to": -80},
    },
    "parallax_fg": {
        "tier": "scrub",
        "display_name": "Parallax foreground",
        "description": "Section slides forward as you scroll past. Subtle pop.",
        "defaults": {"intensity": 0.2, "mobile_mode": "auto"},
        "scrub": {"y_from": 0, "y_to": 50},
    },
    "scale_with_scroll": {
        "tier": "scrub",
        "display_name": "Scale with scroll",
        "description": "Section scales from 0.9 to 1.1 across its scroll range.",
        "defaults": {"intensity": 0.2, "mobile_mode": "auto"},
        "scrub": {"scale_from": 0.9, "scale_to": 1.1},
    },
    "opacity_scrub": {
        "tier": "scrub",
        "display_name": "Opacity scrub",
        "description": "Section fades in, holds, fades out across scroll range.",
        "defaults": {"intensity": 1, "mobile_mode": "auto"},
        "scrub": {"opacity_curve": [0, 1, 1, 0]},
    },
    "pin_and_scrub": {
        "tier": "scrub",
        "display_name": "Pin and scrub",
        "description": "Section pins to viewport for 1.5x its height as you scroll.",
        "defaults": {"intensity": 1.5, "mobile_mode": "auto"},
        "scrub": {"pin": True, "end_height_multiplier": 1.5},
    },
}


def all_presets() -> dict[str, dict]:
    """Merged registry — every preset keyed by id. Used by the GET
    /presets endpoint to render the picker, and by section.animations
    validation to reject unknown preset ids."""
    return {**TIER1_ENTRY, **TIER2_SCRUB}


PRESET_IDS: frozenset[str] = frozenset({
    *TIER1_ENTRY.keys(),
    *TIER2_SCRUB.keys(),
    "default",  # restore variant default behavior
    "none",     # no animation at all
})


def is_valid_preset(preset_id: str) -> bool:
    return preset_id in PRESET_IDS
