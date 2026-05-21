"""Hand-designed SVG schematics for the variant picker cards.

Each schematic is a self-contained inline SVG (no external image hrefs,
no font loads) using the Liquid Glass palette. ViewBox is 400x250 so
the picker card can render at any size via aspect-ratio. Use semantic
shapes (rectangles, paths, gradients) to suggest the variant's layout
without literal screenshots.

Palette (kept in sync with section-editor.css):
  --se-surface       rgba(10, 14, 26, 1)    → #0A0E1A   page bg
  --se-card          rgba(255, 255, 255, 0.04) → ~#1A1F2E approx
  --se-border        rgba(255, 255, 255, 0.12)
  --se-text-bar      rgba(255, 255, 255, 0.08)  → text placeholders
  --se-accent-grad   #00D4FF → #8B5CF6 → #EC4899  → CTAs / accents
"""
from __future__ import annotations

# Shared <defs> block — declared once per SVG. Each schematic embeds
# its own copy to keep self-contained.
_GRADIENT_DEFS = (
    '<defs>'
    '<linearGradient id="lg-accent" x1="0%" y1="0%" x2="100%" y2="0%">'
    '<stop offset="0%" stop-color="#00D4FF"/>'
    '<stop offset="55%" stop-color="#8B5CF6"/>'
    '<stop offset="100%" stop-color="#EC4899"/>'
    '</linearGradient>'
    '<linearGradient id="lg-fade" x1="0%" y1="0%" x2="0%" y2="100%">'
    '<stop offset="0%" stop-color="rgba(15,18,32,0)"/>'
    '<stop offset="100%" stop-color="rgba(15,18,32,0.85)"/>'
    '</linearGradient>'
    '</defs>'
)


SVG_HERO_VIDEO = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Video background hero schematic">'
    + _GRADIENT_DEFS +
    # Full-bleed dark base (video area)
    '<rect width="400" height="250" fill="#0A0E1A"/>'
    # Suggested video frame — slightly lighter rectangle with diagonal "play" hint
    '<rect width="400" height="250" fill="#1A1F2E" opacity="0.6"/>'
    # Diagonal lines suggesting motion
    '<line x1="0" y1="80" x2="400" y2="120" stroke="#FFFFFF" stroke-opacity="0.04" stroke-width="1"/>'
    '<line x1="0" y1="160" x2="400" y2="200" stroke="#FFFFFF" stroke-opacity="0.04" stroke-width="1"/>'
    # Dark gradient overlay bottom half (where text sits)
    '<rect width="400" height="250" fill="url(#lg-fade)"/>'
    # Headline text-bar (wide)
    '<rect x="90" y="118" width="220" height="14" rx="3" fill="rgba(255,255,255,0.95)"/>'
    # Subheadline text-bar (narrower)
    '<rect x="110" y="142" width="180" height="6" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="118" y="156" width="164" height="6" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # Primary CTA pill (accent gradient)
    '<rect x="130" y="185" width="65" height="22" rx="11" fill="url(#lg-accent)"/>'
    # Secondary CTA pill (outlined)
    '<rect x="205" y="185" width="65" height="22" rx="11" fill="none" stroke="rgba(255,255,255,0.42)" stroke-width="1"/>'
    # Play icon top-left (watermark)
    '<circle cx="28" cy="28" r="11" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.32)" stroke-width="0.8"/>'
    '<path d="M 24 22 L 24 34 L 34 28 Z" fill="rgba(255,255,255,0.86)"/>'
    '</svg>'
)


SVG_HERO_TWO_COL_IMAGE = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Two-column with image hero schematic">'
    + _GRADIENT_DEFS +
    # Base
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Left column (60%) — copy
    '<rect x="0" y="0" width="240" height="250" fill="#0F1320"/>'
    # Headline text-bars (large)
    '<rect x="32" y="60" width="170" height="14" rx="3" fill="rgba(255,255,255,0.86)"/>'
    '<rect x="32" y="82" width="140" height="14" rx="3" fill="rgba(255,255,255,0.86)"/>'
    # Subheadline text-bars (smaller)
    '<rect x="32" y="118" width="170" height="6" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="32" y="132" width="156" height="6" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # CTA pair
    '<rect x="32" y="166" width="68" height="22" rx="6" fill="url(#lg-accent)"/>'
    '<rect x="110" y="166" width="68" height="22" rx="6" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)" stroke-width="0.8"/>'
    # Right column (40%) — image area
    '<rect x="248" y="25" width="128" height="200" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.12)" stroke-width="0.8"/>'
    # Mountain/landscape silhouette inside image area
    '<path d="M 260 200 L 290 145 L 312 170 L 332 130 L 360 175 L 372 165 L 372 215 L 260 215 Z" fill="rgba(139,92,246,0.32)"/>'
    '<path d="M 260 200 L 290 145 L 312 170 L 332 130 L 360 175 L 372 165 L 372 215 L 260 215 Z" fill="url(#lg-accent)" opacity="0.18"/>'
    # Sun/accent circle
    '<circle cx="345" cy="65" r="10" fill="url(#lg-accent)" opacity="0.55"/>'
    '</svg>'
)


SVG_HERO_TWO_COL_FORM = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Two-column with lead form hero schematic">'
    + _GRADIENT_DEFS +
    # Base
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Left column (50%) — copy
    # Eyebrow pill
    '<rect x="32" y="40" width="56" height="12" rx="6" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="40" y="44" width="40" height="4" rx="2" fill="rgba(199,210,254,0.86)"/>'
    # Headline bars
    '<rect x="32" y="68" width="140" height="12" rx="3" fill="rgba(255,255,255,0.86)"/>'
    '<rect x="32" y="86" width="120" height="12" rx="3" fill="rgba(255,255,255,0.86)"/>'
    # Sub bars
    '<rect x="32" y="115" width="146" height="5" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="32" y="126" width="130" height="5" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Checklist (3 items)
    '<circle cx="38" cy="158" r="3" fill="#10B981"/>'
    '<rect x="46" y="156" width="110" height="4" rx="2" fill="rgba(255,255,255,0.40)"/>'
    '<circle cx="38" cy="172" r="3" fill="#10B981"/>'
    '<rect x="46" y="170" width="96" height="4" rx="2" fill="rgba(255,255,255,0.40)"/>'
    '<circle cx="38" cy="186" r="3" fill="#10B981"/>'
    '<rect x="46" y="184" width="84" height="4" rx="2" fill="rgba(255,255,255,0.40)"/>'
    # Right column (50%) — form card
    '<rect x="212" y="38" width="156" height="180" rx="10" fill="#FFFFFF" opacity="0.96"/>'
    # Form labels + fields
    '<rect x="225" y="52" width="44" height="5" rx="2" fill="rgba(31,41,55,0.42)"/>'
    '<rect x="225" y="62" width="130" height="14" rx="3" fill="rgba(229,231,235,1)"/>'
    '<rect x="225" y="84" width="44" height="5" rx="2" fill="rgba(31,41,55,0.42)"/>'
    '<rect x="225" y="94" width="130" height="14" rx="3" fill="rgba(229,231,235,1)"/>'
    '<rect x="225" y="116" width="44" height="5" rx="2" fill="rgba(31,41,55,0.42)"/>'
    '<rect x="225" y="126" width="130" height="14" rx="3" fill="rgba(229,231,235,1)"/>'
    '<rect x="225" y="148" width="62" height="5" rx="2" fill="rgba(31,41,55,0.42)"/>'
    '<rect x="225" y="158" width="130" height="24" rx="3" fill="rgba(229,231,235,1)"/>'
    # Submit button (accent gradient)
    '<rect x="225" y="190" width="130" height="18" rx="4" fill="url(#lg-accent)"/>'
    '</svg>'
)


SVG_HERO_WITH_STATS = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Hero with stats schematic">'
    + _GRADIENT_DEFS +
    # Base
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Top 60% — centered hero
    # Eyebrow pill
    '<rect x="160" y="32" width="80" height="12" rx="6" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="172" y="36" width="56" height="4" rx="2" fill="rgba(199,210,254,0.86)"/>'
    # Headline bars (centered)
    '<rect x="80" y="62" width="240" height="13" rx="3" fill="rgba(255,255,255,0.88)"/>'
    '<rect x="120" y="80" width="160" height="13" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # Sub bars
    '<rect x="110" y="108" width="180" height="5" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="130" y="120" width="140" height="5" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # CTAs
    '<rect x="140" y="138" width="56" height="18" rx="4" fill="url(#lg-accent)"/>'
    '<rect x="204" y="138" width="56" height="18" rx="4" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)" stroke-width="0.8"/>'
    # Divider line
    '<line x1="40" y1="178" x2="360" y2="178" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
    # Bottom 40% — 4-stat strip
    # Stat 1
    '<rect x="50" y="192" width="40" height="14" rx="2" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="52" y="212" width="36" height="4" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # Stat 2
    '<rect x="138" y="192" width="40" height="14" rx="2" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="140" y="212" width="36" height="4" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # Stat 3
    '<rect x="226" y="192" width="40" height="14" rx="2" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="228" y="212" width="36" height="4" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # Stat 4
    '<rect x="314" y="192" width="40" height="14" rx="2" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="316" y="212" width="36" height="4" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '</svg>'
)


SCHEMATICS_BY_VARIANT_ID: dict[str, str] = {
    "hero_video": SVG_HERO_VIDEO,
    "hero_two_col_image": SVG_HERO_TWO_COL_IMAGE,
    "hero_two_col_form": SVG_HERO_TWO_COL_FORM,
    "hero_with_stats": SVG_HERO_WITH_STATS,
}
