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


SVG_FEATURES_3COL_ICON = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="3-column features grid schematic">'
    + _GRADIENT_DEFS +
    # Base
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Top: eyebrow pill + headline + subheadline (centered)
    '<rect x="160" y="18" width="80" height="10" rx="5" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="100" y="38" width="200" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    '<rect x="130" y="56" width="140" height="6" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # 6 cards in 3x2 grid. Card geometry: 110w × 70h, gutter 8px.
    # Top row y=82, bottom row y=164. x starts at 25, 145, 265.
    # Card 1 (indigo→violet)
    '<rect x="25" y="82" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="35" y="92" width="18" height="18" rx="4" fill="url(#lg-accent)"/>'
    '<rect x="35" y="118" width="64" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="35" y="130" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="35" y="138" width="62" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Card 2
    '<rect x="145" y="82" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="155" y="92" width="18" height="18" rx="4" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="155" y="118" width="68" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="155" y="130" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="155" y="138" width="58" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Card 3
    '<rect x="265" y="82" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="275" y="92" width="18" height="18" rx="4" fill="url(#lg-accent)" opacity="0.70"/>'
    '<rect x="275" y="118" width="58" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="275" y="130" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="275" y="138" width="66" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Card 4 (bottom row)
    '<rect x="25" y="164" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="35" y="174" width="18" height="18" rx="4" fill="url(#lg-accent)" opacity="0.65"/>'
    '<rect x="35" y="200" width="64" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="35" y="212" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="35" y="220" width="62" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Card 5
    '<rect x="145" y="164" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="155" y="174" width="18" height="18" rx="4" fill="url(#lg-accent)" opacity="0.55"/>'
    '<rect x="155" y="200" width="62" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="155" y="212" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="155" y="220" width="58" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    # Card 6
    '<rect x="265" y="164" width="110" height="70" rx="8" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="275" y="174" width="18" height="18" rx="4" fill="url(#lg-accent)" opacity="0.45"/>'
    '<rect x="275" y="200" width="60" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="275" y="212" width="80" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="275" y="220" width="68" height="4" rx="2" fill="rgba(255,255,255,0.30)"/>'
    '</svg>'
)


SVG_CTA_CENTERED_BANNER = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Centered CTA banner schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Gradient banner panel (rounded) — the focal element
    '<rect x="40" y="55" width="320" height="140" rx="20" fill="url(#lg-accent)" opacity="0.85"/>'
    # White-ish highlight to suggest the radial top-right glow
    '<ellipse cx="320" cy="80" rx="80" ry="50" fill="rgba(255,255,255,0.16)"/>'
    # Eyebrow pill
    '<rect x="170" y="80" width="60" height="10" rx="5" fill="rgba(255,255,255,0.40)"/>'
    # Headline
    '<rect x="100" y="100" width="200" height="14" rx="3" fill="rgba(255,255,255,0.96)"/>'
    '<rect x="130" y="120" width="140" height="14" rx="3" fill="rgba(255,255,255,0.96)"/>'
    # Sub
    '<rect x="120" y="142" width="160" height="6" rx="2" fill="rgba(255,255,255,0.65)"/>'
    # 2 CTA pills (white solid + outlined)
    '<rect x="140" y="160" width="55" height="20" rx="10" fill="rgba(255,255,255,0.96)"/>'
    '<rect x="205" y="160" width="55" height="20" rx="10" fill="none" stroke="rgba(255,255,255,0.78)" stroke-width="1.5"/>'
    '</svg>'
)


SVG_PRICING_3TIER_FEATURED = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="3-tier pricing with featured middle schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Top eyebrow + headline
    '<rect x="170" y="18" width="60" height="8" rx="4" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="110" y="32" width="180" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # Three tier cards. Middle one elevated (y -8) + accent border + larger.
    # Left card (Starter)
    '<rect x="22" y="64" width="112" height="170" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.10)"/>'
    '<rect x="32" y="76" width="48" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="32" y="94" width="42" height="14" rx="2" fill="rgba(255,255,255,0.92)"/>'
    '<rect x="32" y="120" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="32" y="130" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="32" y="140" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="32" y="208" width="92" height="16" rx="6" fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.20)" stroke-width="0.8"/>'
    # Middle card (Pro — featured)
    '<rect x="142" y="54" width="116" height="190" rx="12" fill="url(#lg-accent)" opacity="0.18"/>'
    '<rect x="142" y="54" width="116" height="190" rx="12" fill="none" stroke="rgba(99,102,241,0.85)" stroke-width="2"/>'
    # "Most Popular" pill
    '<rect x="176" y="46" width="48" height="14" rx="7" fill="url(#lg-accent)"/>'
    '<rect x="152" y="76" width="40" height="6" rx="2" fill="rgba(255,255,255,0.96)"/>'
    '<rect x="152" y="94" width="56" height="16" rx="2" fill="url(#lg-accent)"/>'
    '<rect x="152" y="124" width="84" height="3" rx="1.5" fill="rgba(255,255,255,0.45)"/>'
    '<rect x="152" y="134" width="84" height="3" rx="1.5" fill="rgba(255,255,255,0.45)"/>'
    '<rect x="152" y="144" width="84" height="3" rx="1.5" fill="rgba(255,255,255,0.45)"/>'
    '<rect x="152" y="154" width="84" height="3" rx="1.5" fill="rgba(255,255,255,0.45)"/>'
    '<rect x="152" y="216" width="96" height="18" rx="6" fill="url(#lg-accent)"/>'
    # Right card (Enterprise)
    '<rect x="266" y="64" width="112" height="170" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.10)"/>'
    '<rect x="276" y="76" width="62" height="6" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="276" y="94" width="56" height="14" rx="2" fill="rgba(255,255,255,0.92)"/>'
    '<rect x="276" y="120" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="276" y="130" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="276" y="140" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="276" y="208" width="92" height="16" rx="6" fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.20)" stroke-width="0.8"/>'
    '</svg>'
)


SVG_TESTIMONIALS_3CARD = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="3-card testimonials schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="18" width="60" height="8" rx="4" fill="rgba(236,72,153,0.32)"/>'
    '<rect x="120" y="32" width="160" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # 3 testimonial cards
    # Card 1
    '<rect x="22" y="74" width="112" height="160" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    # Quote mark
    '<text x="34" y="100" font-family="serif" font-size="22" font-weight="700" fill="rgba(99,102,241,0.55)">"</text>'
    '<rect x="32" y="110" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="32" y="120" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="32" y="130" width="80" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="32" y="140" width="72" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<circle cx="44" cy="200" r="12" fill="url(#lg-accent)"/>'
    '<rect x="62" y="194" width="50" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="62" y="204" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    # Card 2
    '<rect x="144" y="74" width="112" height="160" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<text x="156" y="100" font-family="serif" font-size="22" font-weight="700" fill="rgba(6,182,212,0.55)">"</text>'
    '<rect x="154" y="110" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="154" y="120" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="154" y="130" width="86" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="154" y="140" width="76" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<circle cx="166" cy="200" r="12" fill="url(#lg-accent)" opacity="0.80"/>'
    '<rect x="184" y="194" width="50" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="184" y="204" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    # Card 3
    '<rect x="266" y="74" width="112" height="160" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<text x="278" y="100" font-family="serif" font-size="22" font-weight="700" fill="rgba(16,185,129,0.55)">"</text>'
    '<rect x="276" y="110" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="276" y="120" width="92" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="276" y="130" width="84" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<rect x="276" y="140" width="70" height="3" rx="1.5" fill="rgba(255,255,255,0.35)"/>'
    '<circle cx="288" cy="200" r="12" fill="url(#lg-accent)" opacity="0.60"/>'
    '<rect x="306" y="194" width="50" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="306" y="204" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '</svg>'
)


SVG_TEAM_PHOTO_GRID_3COL = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="3-column team photo grid schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="14" width="60" height="8" rx="4" fill="rgba(16,185,129,0.32)"/>'
    '<rect x="110" y="28" width="180" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # 6 member cards in 3x2 grid. Each card has avatar circle + 2 text bars.
    # Card width 112, height 78. x at 22, 144, 266. y at 58, 148.
    # Row 1
    '<rect x="22" y="58" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="78" cy="85" r="16" fill="url(#lg-accent)"/>'
    '<rect x="50" y="110" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="58" y="120" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="144" y="58" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="200" cy="85" r="16" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="172" y="110" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="180" y="120" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="266" y="58" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="322" cy="85" r="16" fill="url(#lg-accent)" opacity="0.70"/>'
    '<rect x="294" y="110" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="302" y="120" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    # Row 2
    '<rect x="22" y="148" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="78" cy="175" r="16" fill="url(#lg-accent)" opacity="0.65"/>'
    '<rect x="50" y="200" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="58" y="210" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="144" y="148" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="200" cy="175" r="16" fill="url(#lg-accent)" opacity="0.55"/>'
    '<rect x="172" y="200" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="180" y="210" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="266" y="148" width="112" height="78" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="322" cy="175" r="16" fill="url(#lg-accent)" opacity="0.45"/>'
    '<rect x="294" y="200" width="56" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="302" y="210" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '</svg>'
)


SVG_STATS_4COL_HORIZONTAL = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="4-column stats schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="32" width="60" height="8" rx="4" fill="rgba(6,182,212,0.32)"/>'
    '<rect x="100" y="48" width="200" height="11" rx="3" fill="rgba(255,255,255,0.88)"/>'
    '<rect x="130" y="68" width="140" height="5" rx="2" fill="rgba(255,255,255,0.32)"/>'
    # 4 big stat numbers — large gradient blocks + small labels
    '<rect x="38" y="110" width="62" height="44" rx="6" fill="url(#lg-accent)"/>'
    '<rect x="42" y="166" width="54" height="5" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="48" y="178" width="42" height="3" rx="1.5" fill="rgba(255,255,255,0.22)"/>'
    '<rect x="118" y="110" width="62" height="44" rx="6" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="122" y="166" width="54" height="5" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="128" y="178" width="42" height="3" rx="1.5" fill="rgba(255,255,255,0.22)"/>'
    '<rect x="218" y="110" width="62" height="44" rx="6" fill="url(#lg-accent)" opacity="0.70"/>'
    '<rect x="222" y="166" width="54" height="5" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="228" y="178" width="42" height="3" rx="1.5" fill="rgba(255,255,255,0.22)"/>'
    '<rect x="298" y="110" width="62" height="44" rx="6" fill="url(#lg-accent)" opacity="0.55"/>'
    '<rect x="302" y="166" width="54" height="5" rx="2" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="308" y="178" width="42" height="3" rx="1.5" fill="rgba(255,255,255,0.22)"/>'
    '</svg>'
)


SVG_FAQ_ACCORDION = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="FAQ accordion schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="18" width="60" height="8" rx="4" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="100" y="32" width="200" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # Accordion rows. First one OPEN (expanded with answer text), the rest collapsed.
    # Open row
    '<rect x="80" y="60" width="240" height="56" rx="8" fill="#1A1F2E" stroke="rgba(99,102,241,0.40)"/>'
    '<rect x="92" y="72" width="160" height="6" rx="2" fill="rgba(255,255,255,0.85)"/>'
    '<path d="M 304 73 L 308 77 L 312 73" stroke="rgba(255,255,255,0.55)" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '<rect x="92" y="90" width="216" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="92" y="100" width="200" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    # Collapsed rows
    '<rect x="80" y="124" width="240" height="22" rx="6" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="92" y="132" width="180" height="6" rx="2" fill="rgba(255,255,255,0.62)"/>'
    '<path d="M 304 133 L 308 137 L 312 133" stroke="rgba(255,255,255,0.45)" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '<rect x="80" y="154" width="240" height="22" rx="6" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="92" y="162" width="160" height="6" rx="2" fill="rgba(255,255,255,0.62)"/>'
    '<path d="M 304 163 L 308 167 L 312 163" stroke="rgba(255,255,255,0.45)" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '<rect x="80" y="184" width="240" height="22" rx="6" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="92" y="192" width="190" height="6" rx="2" fill="rgba(255,255,255,0.62)"/>'
    '<path d="M 304 193 L 308 197 L 312 193" stroke="rgba(255,255,255,0.45)" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '<rect x="80" y="214" width="240" height="22" rx="6" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="92" y="222" width="170" height="6" rx="2" fill="rgba(255,255,255,0.62)"/>'
    '<path d="M 304 223 L 308 227 L 312 223" stroke="rgba(255,255,255,0.45)" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '</svg>'
)


SVG_CONTACT_FORM_PLUS_INFO = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Contact form plus info schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="14" width="60" height="8" rx="4" fill="rgba(99,102,241,0.32)"/>'
    '<rect x="110" y="28" width="180" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # Form card (left, larger) — 3/5 of width
    '<rect x="22" y="58" width="232" height="180" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    # 2-col field row
    '<rect x="34" y="74" width="46" height="5" rx="2" fill="rgba(255,255,255,0.42)"/>'
    '<rect x="34" y="84" width="100" height="16" rx="3" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    '<rect x="142" y="74" width="58" height="5" rx="2" fill="rgba(255,255,255,0.42)"/>'
    '<rect x="142" y="84" width="100" height="16" rx="3" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    # Single field
    '<rect x="34" y="110" width="48" height="5" rx="2" fill="rgba(255,255,255,0.42)"/>'
    '<rect x="34" y="120" width="208" height="16" rx="3" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    # Textarea
    '<rect x="34" y="146" width="80" height="5" rx="2" fill="rgba(255,255,255,0.42)"/>'
    '<rect x="34" y="156" width="208" height="38" rx="3" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    # Submit button
    '<rect x="34" y="204" width="208" height="20" rx="5" fill="url(#lg-accent)"/>'
    # Info column (right) — 2/5 of width, 3 stacked info cards
    '<rect x="266" y="58" width="112" height="54" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="276" y="74" width="20" height="20" rx="5" fill="url(#lg-accent)"/>'
    '<rect x="304" y="78" width="48" height="4" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="304" y="88" width="64" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="266" y="120" width="112" height="54" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="276" y="136" width="20" height="20" rx="5" fill="url(#lg-accent)" opacity="0.85"/>'
    '<rect x="304" y="140" width="42" height="4" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="304" y="150" width="64" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="266" y="182" width="112" height="54" rx="10" fill="#1A1F2E" stroke="rgba(255,255,255,0.08)"/>'
    '<rect x="276" y="198" width="20" height="20" rx="5" fill="url(#lg-accent)" opacity="0.70"/>'
    '<rect x="304" y="202" width="48" height="4" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="304" y="212" width="64" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="304" y="222" width="58" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '</svg>'
)


SVG_FOOTER_4COL = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="4-column footer schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    # Top border (suggests this is the bottom of a page)
    '<line x1="0" y1="32" x2="400" y2="32" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>'
    # Brand col (wider — spans 2 of 5)
    '<rect x="22" y="56" width="22" height="22" rx="5" fill="url(#lg-accent)"/>'
    '<rect x="50" y="62" width="68" height="8" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="22" y="92" width="120" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="22" y="102" width="100" height="3" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    # Col 1
    '<rect x="172" y="56" width="40" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="172" y="74" width="56" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="172" y="86" width="48" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="172" y="98" width="60" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="172" y="110" width="50" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    # Col 2
    '<rect x="242" y="56" width="40" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="242" y="74" width="44" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="242" y="86" width="52" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="242" y="98" width="56" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="242" y="110" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    # Col 3
    '<rect x="312" y="56" width="48" height="5" rx="2" fill="rgba(255,255,255,0.78)"/>'
    '<rect x="312" y="74" width="60" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="312" y="86" width="40" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="312" y="98" width="52" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    '<rect x="312" y="110" width="36" height="3" rx="1.5" fill="rgba(255,255,255,0.30)"/>'
    # Bottom border + copyright + social icons
    '<line x1="20" y1="180" x2="380" y2="180" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>'
    '<rect x="22" y="200" width="140" height="4" rx="1.5" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="296" y="194" width="20" height="20" rx="5" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    '<rect x="322" y="194" width="20" height="20" rx="5" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    '<rect x="348" y="194" width="20" height="20" rx="5" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.10)"/>'
    '</svg>'
)


SVG_GALLERY_MASONRY = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Masonry gallery schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="14" width="60" height="8" rx="4" fill="rgba(236,72,153,0.32)"/>'
    '<rect x="120" y="28" width="160" height="10" rx="3" fill="rgba(255,255,255,0.88)"/>'
    # Masonry: 3 columns of varied-height images.
    # Col 1 (x=22, w=110)
    '<rect x="22" y="54" width="110" height="64" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 32 100 L 50 80 L 65 92 L 78 78 L 95 96 L 120 90 L 120 110 L 32 110 Z" fill="url(#lg-accent)" opacity="0.32"/>'
    '<rect x="22" y="126" width="110" height="44" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="78" cy="148" r="10" fill="url(#lg-accent)" opacity="0.55"/>'
    '<rect x="22" y="178" width="110" height="56" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 32 218 L 56 200 L 78 210 L 100 198 L 120 220 L 32 220 Z" fill="url(#lg-accent)" opacity="0.42"/>'
    # Col 2 (x=144)
    '<rect x="144" y="54" width="110" height="44" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="200" cy="74" r="10" fill="url(#lg-accent)" opacity="0.48"/>'
    '<rect x="144" y="106" width="110" height="72" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 156 160 L 180 130 L 200 145 L 220 128 L 244 155 L 244 168 L 156 168 Z" fill="url(#lg-accent)" opacity="0.32"/>'
    '<rect x="144" y="186" width="110" height="48" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 156 220 L 180 206 L 200 212 L 224 202 L 244 218 L 244 224 L 156 224 Z" fill="url(#lg-accent)" opacity="0.40"/>'
    # Col 3 (x=266)
    '<rect x="266" y="54" width="110" height="68" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 278 110 L 302 88 L 322 100 L 340 86 L 366 108 L 366 116 L 278 116 Z" fill="url(#lg-accent)" opacity="0.32"/>'
    '<rect x="266" y="130" width="110" height="50" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<circle cx="322" cy="152" r="11" fill="url(#lg-accent)" opacity="0.40"/>'
    '<rect x="266" y="188" width="110" height="46" rx="8" fill="#22293A" stroke="rgba(255,255,255,0.08)"/>'
    '<path d="M 278 222 L 302 208 L 322 216 L 346 204 L 366 220 L 366 226 L 278 226 Z" fill="url(#lg-accent)" opacity="0.45"/>'
    '</svg>'
)


SVG_LOGOS_MARQUEE = (
    '<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg" '
    'preserveAspectRatio="xMidYMid slice" role="img" '
    'aria-label="Logo marquee schematic">'
    + _GRADIENT_DEFS +
    '<rect width="400" height="250" fill="#0F1320"/>'
    '<rect x="170" y="58" width="60" height="8" rx="4" fill="rgba(6,182,212,0.32)"/>'
    '<rect x="100" y="72" width="200" height="8" rx="3" fill="rgba(255,255,255,0.42)"/>'
    # Horizontal logo strip — 6 visible "logos" rendered as text-bar
    # shapes of varied widths, with fade-edges to suggest the marquee
    # continues off-screen.
    '<rect x="36" y="130" width="60" height="14" rx="3" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="118" y="130" width="46" height="14" rx="3" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="186" y="130" width="68" height="14" rx="3" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="276" y="130" width="50" height="14" rx="3" fill="rgba(255,255,255,0.32)"/>'
    '<rect x="346" y="130" width="38" height="14" rx="3" fill="rgba(255,255,255,0.32)"/>'
    # Motion lines beneath suggesting horizontal scroll
    '<line x1="40" y1="166" x2="100" y2="166" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
    '<line x1="120" y1="166" x2="180" y2="166" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
    '<line x1="200" y1="166" x2="260" y2="166" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
    '<line x1="280" y1="166" x2="340" y2="166" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
    # Fade-edge gradients at left + right (simulated via overlay rects)
    '<defs>'
    '<linearGradient id="fade-left" x1="0%" y1="0%" x2="100%" y2="0%">'
    '<stop offset="0%" stop-color="#0F1320" stop-opacity="1"/>'
    '<stop offset="100%" stop-color="#0F1320" stop-opacity="0"/>'
    '</linearGradient>'
    '<linearGradient id="fade-right" x1="0%" y1="0%" x2="100%" y2="0%">'
    '<stop offset="0%" stop-color="#0F1320" stop-opacity="0"/>'
    '<stop offset="100%" stop-color="#0F1320" stop-opacity="1"/>'
    '</linearGradient>'
    '</defs>'
    '<rect x="0" y="110" width="40" height="60" fill="url(#fade-left)"/>'
    '<rect x="360" y="110" width="40" height="60" fill="url(#fade-right)"/>'
    # Small "▶" indicator showing direction of marquee
    '<path d="M 196 200 L 204 196 L 204 204 Z" fill="rgba(255,255,255,0.32)"/>'
    '</svg>'
)


SCHEMATICS_BY_VARIANT_ID: dict[str, str] = {
    "hero_video": SVG_HERO_VIDEO,
    "hero_two_col_image": SVG_HERO_TWO_COL_IMAGE,
    "hero_two_col_form": SVG_HERO_TWO_COL_FORM,
    "hero_with_stats": SVG_HERO_WITH_STATS,
    "features_3col_icon": SVG_FEATURES_3COL_ICON,
    "cta_centered_banner": SVG_CTA_CENTERED_BANNER,
    "pricing_3tier_featured": SVG_PRICING_3TIER_FEATURED,
    "testimonials_3card_grid": SVG_TESTIMONIALS_3CARD,
    "team_photo_grid_3col": SVG_TEAM_PHOTO_GRID_3COL,
    "stats_4col_horizontal": SVG_STATS_4COL_HORIZONTAL,
    "faq_accordion": SVG_FAQ_ACCORDION,
    "contact_form_plus_info": SVG_CONTACT_FORM_PLUS_INFO,
    "footer_4col": SVG_FOOTER_4COL,
    "gallery_masonry": SVG_GALLERY_MASONRY,
    "logos_marquee": SVG_LOGOS_MARQUEE,
}
