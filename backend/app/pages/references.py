"""Reference design selection for AI page generation.

Selects the most relevant reference screenshots and code based on the user's prompt,
then formats them for the Gemini multimodal API.
"""
import base64
import os
from pathlib import Path

# Base path for reference designs
REFERENCES_DIR = Path(__file__).resolve().parent.parent.parent / "reference-designs"
SCREENSHOTS_DIR = REFERENCES_DIR / "screenshots"
CODE_DIR = REFERENCES_DIR / "code"

# Reference design descriptions for the AI
REFERENCE_DESCRIPTIONS = {
    "bensimon": (
        "Family dental, video hero, blue accent (#007AFF), Apple-inspired dark/light, "
        "glassmorphic nav, auto-scrolling testimonial columns, animated star ratings, "
        "scroll reveal, massive typography, squircle cards"
    ),
    "biscayne": (
        "Dental & facial aesthetics, gold/warm (#C8952E), split hero (text+portrait), "
        "feature cards, Why Choose Us checklist, embedded appointment form, testimonials"
    ),
    "maydental": (
        "Centre Mall Dental, rose/coral (#F43F5E), video hero, glassmorphic nav, "
        "inline booking form, doctor profile cards, services icon grid, photo gallery, "
        "FAQ accordion, location map"
    ),
    "ocidm": (
        "Digital agency, DARK LUXURY, purple/orange, animated floating shapes, "
        "MPG framework with interactive tabs, case study cards, pricing tiers, "
        "stats counters, gradient CTAs — works for ANY non-medical industry"
    ),
    "parkdale": (
        "Dentistry on Parkdale, green (#00bf63), clean white, family photo hero, "
        "numbered How We're Different, services icon grid + treatment tags, "
        "Three Pillars section, auto-scrolling testimonials, minimal CTA"
    ),
}


def select_references(user_prompt: str) -> tuple[list[str], str]:
    """Select the best reference screenshots and code file based on user prompt.

    Returns:
        (screenshot_names, code_name) — e.g. (['bensimon', 'biscayne'], 'bensimon')
    """
    prompt_lower = user_prompt.lower()

    # Dark/luxury/tech themes
    if any(w in prompt_lower for w in [
        "agency", "marketing", "tech", "saas", "startup", "dark",
        "luxury", "modern", "creative", "digital", "software",
    ]):
        return ["ocidm", "bensimon"], "ocidm"

    # Medical/dental/health
    if any(w in prompt_lower for w in [
        "dental", "dentist", "doctor", "medical", "clinic", "health",
        "wellness", "spa", "therapy", "chiropractic", "optometry",
    ]):
        return ["bensimon", "biscayne", "parkdale"], "bensimon"

    # Clean/corporate/professional
    if any(w in prompt_lower for w in [
        "law", "consulting", "finance", "real estate", "professional",
        "corporate", "accounting", "insurance", "advisory",
    ]):
        return ["biscayne", "parkdale"], "biscayne"

    # Restaurant/food/retail
    if any(w in prompt_lower for w in [
        "restaurant", "food", "cafe", "coffee", "store", "shop",
        "retail", "bakery", "bar", "catering",
    ]):
        return ["biscayne", "maydental"], "maydental"

    # Education/nonprofit
    if any(w in prompt_lower for w in [
        "school", "university", "education", "nonprofit", "charity",
        "church", "community",
    ]):
        return ["parkdale", "biscayne"], "parkdale"

    # Default — send variety
    return ["ocidm", "bensimon", "biscayne"], "bensimon"


def load_screenshot_base64(name: str) -> str | None:
    """Load a compressed JPEG screenshot as base64 string."""
    jpg_path = SCREENSHOTS_DIR / f"{name}.jpg"
    if not jpg_path.exists():
        # Fall back to PNG
        png_path = SCREENSHOTS_DIR / f"{name}.png"
        if not png_path.exists():
            return None
        with open(png_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("ascii")
    with open(jpg_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


def load_reference_code(name: str) -> str | None:
    """Load a reference HTML code file."""
    html_path = CODE_DIR / f"{name}.html"
    if not html_path.exists():
        return None
    return html_path.read_text(encoding="utf-8", errors="replace")


def get_screenshot_mime(name: str) -> str:
    """Get MIME type for a screenshot."""
    jpg_path = SCREENSHOTS_DIR / f"{name}.jpg"
    return "image/jpeg" if jpg_path.exists() else "image/png"


def build_reference_parts(
    user_prompt: str,
) -> tuple[list[dict], str]:
    """Build Gemini multimodal parts with reference screenshots and code.

    Returns:
        (image_parts, reference_text) — image_parts for Gemini API, reference_text with code
    """
    screenshot_names, code_name = select_references(user_prompt)

    # Build image parts for Gemini multimodal API
    image_parts = []
    loaded_names = []
    for name in screenshot_names:
        b64 = load_screenshot_base64(name)
        if b64:
            mime = get_screenshot_mime(name)
            image_parts.append({
                "inlineData": {
                    "mimeType": mime,
                    "data": b64,
                }
            })
            loaded_names.append(name)

    # Build descriptions of what was sent
    desc_lines = []
    for name in loaded_names:
        desc = REFERENCE_DESCRIPTIONS.get(name, "")
        desc_lines.append(f"  - {name}: {desc}")
    descriptions = "\n".join(desc_lines)

    # Load reference code
    code_html = load_reference_code(code_name) or ""
    # Truncate very long code to stay within token limits (keep first 40K chars)
    if len(code_html) > 40000:
        code_html = code_html[:40000] + "\n<!-- ... truncated ... -->"

    reference_text = (
        "The images above show the EXACT quality and style level I want. "
        "Study them carefully — these are $50,000 professional websites.\n\n"
        f"Reference designs shown:\n{descriptions}\n\n"
        "Here is the code that produced one of these premium designs — "
        "use the same patterns, structure, and techniques:\n\n"
        f"```html\n{code_html}\n```\n\n"
        "Now build a NEW website with the SAME premium quality but a DIFFERENT layout. "
        "Match the quality of these references EXACTLY."
    )

    return image_parts, reference_text
