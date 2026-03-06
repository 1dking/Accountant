"""Business logic for the AI page builder module."""

import json
import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.pages.models import Page, PageAnalytic, PageStatus, PageVersion


# ---------------------------------------------------------------------------
# Style presets
# ---------------------------------------------------------------------------

STYLE_PRESETS = {
    "modern": {
        "id": "modern",
        "name": "Modern",
        "description": "Clean, minimalist design with bold typography",
        "preview_colors": {"primary": "#2563eb", "bg": "#ffffff", "text": "#111827"},
    },
    "corporate": {
        "id": "corporate",
        "name": "Corporate",
        "description": "Professional and trustworthy business aesthetic",
        "preview_colors": {"primary": "#1e40af", "bg": "#f8fafc", "text": "#1e293b"},
    },
    "creative": {
        "id": "creative",
        "name": "Creative",
        "description": "Bold gradients, vibrant colors, dynamic layout",
        "preview_colors": {"primary": "#7c3aed", "bg": "#faf5ff", "text": "#1e1b4b"},
    },
    "startup": {
        "id": "startup",
        "name": "Startup",
        "description": "Fresh, energetic SaaS-style landing page",
        "preview_colors": {"primary": "#06b6d4", "bg": "#ecfeff", "text": "#164e63"},
    },
    "elegant": {
        "id": "elegant",
        "name": "Elegant",
        "description": "Sophisticated serif fonts, muted tones",
        "preview_colors": {"primary": "#92400e", "bg": "#fffbeb", "text": "#451a03"},
    },
    "dark": {
        "id": "dark",
        "name": "Dark",
        "description": "Dark background with neon accents",
        "preview_colors": {"primary": "#22d3ee", "bg": "#0f172a", "text": "#f1f5f9"},
    },
}


# ---------------------------------------------------------------------------
# Section templates
# ---------------------------------------------------------------------------

SECTION_TEMPLATES = [
    {
        "id": "hero_centered",
        "type": "hero",
        "name": "Hero — Centered",
        "description": "Large headline, subtitle, and CTA centered on page",
        "default_html": '<section class="hero"><div class="container mx-auto text-center py-24 px-6"><h1 class="text-5xl font-bold mb-6">{{headline}}</h1><p class="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">{{subtitle}}</p><a href="#" class="btn-primary px-8 py-3 rounded-lg text-lg font-semibold">{{cta_text}}</a></div></section>',
    },
    {
        "id": "hero_split",
        "type": "hero",
        "name": "Hero — Split",
        "description": "Text on left, image on right, with CTA",
        "default_html": '<section class="hero"><div class="container mx-auto grid md:grid-cols-2 gap-12 items-center py-20 px-6"><div><h1 class="text-5xl font-bold mb-6">{{headline}}</h1><p class="text-xl text-gray-600 mb-8">{{subtitle}}</p><a href="#" class="btn-primary px-8 py-3 rounded-lg">{{cta_text}}</a></div><div><img src="{{image_url}}" alt="" class="rounded-xl shadow-lg w-full"/></div></div></section>',
    },
    {
        "id": "features_grid",
        "type": "features",
        "name": "Features — 3-Column Grid",
        "description": "Three feature cards with icons",
        "default_html": '<section class="features py-20 px-6"><div class="container mx-auto"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="grid md:grid-cols-3 gap-8">{{#features}}<div class="p-6 rounded-xl border"><div class="text-3xl mb-4">{{icon}}</div><h3 class="text-xl font-semibold mb-2">{{title}}</h3><p class="text-gray-600">{{description}}</p></div>{{/features}}</div></div></section>',
    },
    {
        "id": "features_alternating",
        "type": "features",
        "name": "Features — Alternating",
        "description": "Image-text alternating rows",
        "default_html": '<section class="features py-20 px-6"><div class="container mx-auto space-y-20">{{#features}}<div class="grid md:grid-cols-2 gap-12 items-center"><div><h3 class="text-2xl font-bold mb-4">{{title}}</h3><p class="text-gray-600">{{description}}</p></div><div><img src="{{image_url}}" alt="" class="rounded-xl shadow-lg w-full"/></div></div>{{/features}}</div></section>',
    },
    {
        "id": "pricing_three_tier",
        "type": "pricing",
        "name": "Pricing — Three Tiers",
        "description": "Standard three-column pricing table",
        "default_html": '<section class="pricing py-20 px-6 bg-gray-50"><div class="container mx-auto"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">{{#plans}}<div class="bg-white p-8 rounded-xl shadow-sm border"><h3 class="text-xl font-semibold mb-2">{{name}}</h3><div class="text-4xl font-bold mb-4">{{price}}</div><p class="text-gray-500 mb-6">{{description}}</p><ul class="space-y-3 mb-8">{{#features}}<li>✓ {{.}}</li>{{/features}}</ul><a href="#" class="btn-primary block text-center px-6 py-3 rounded-lg">Get Started</a></div>{{/plans}}</div></div></section>',
    },
    {
        "id": "testimonials_cards",
        "type": "testimonials",
        "name": "Testimonials — Cards",
        "description": "Client testimonial cards with quotes",
        "default_html": '<section class="testimonials py-20 px-6"><div class="container mx-auto"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="grid md:grid-cols-3 gap-8">{{#testimonials}}<div class="bg-white p-6 rounded-xl shadow-sm border"><p class="text-gray-600 mb-4">"{{quote}}"</p><div class="flex items-center gap-3"><div class="w-10 h-10 rounded-full bg-gray-200"></div><div><p class="font-semibold">{{name}}</p><p class="text-sm text-gray-500">{{role}}</p></div></div></div>{{/testimonials}}</div></div></section>',
    },
    {
        "id": "cta_banner",
        "type": "cta",
        "name": "CTA — Banner",
        "description": "Full-width call-to-action banner",
        "default_html": '<section class="cta py-16 px-6 bg-blue-600 text-white"><div class="container mx-auto text-center"><h2 class="text-3xl font-bold mb-4">{{heading}}</h2><p class="text-xl opacity-90 mb-8 max-w-2xl mx-auto">{{subtitle}}</p><a href="#" class="bg-white text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-blue-50 transition">{{cta_text}}</a></div></section>',
    },
    {
        "id": "faq_accordion",
        "type": "faq",
        "name": "FAQ — Accordion",
        "description": "Expandable FAQ items",
        "default_html": '<section class="faq py-20 px-6"><div class="container mx-auto max-w-3xl"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="space-y-4">{{#faqs}}<details class="border rounded-lg p-4"><summary class="font-semibold cursor-pointer">{{question}}</summary><p class="mt-3 text-gray-600">{{answer}}</p></details>{{/faqs}}</div></div></section>',
    },
    {
        "id": "about_team",
        "type": "about",
        "name": "About — Team Grid",
        "description": "Team member photo grid with bios",
        "default_html": '<section class="about py-20 px-6"><div class="container mx-auto"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="grid md:grid-cols-4 gap-8">{{#members}}<div class="text-center"><div class="w-24 h-24 rounded-full bg-gray-200 mx-auto mb-4"></div><h3 class="font-semibold">{{name}}</h3><p class="text-gray-500 text-sm">{{role}}</p></div>{{/members}}</div></div></section>',
    },
    {
        "id": "contact_form_simple",
        "type": "contact_form",
        "name": "Contact — Simple Form",
        "description": "Name, email, message contact form",
        "default_html": '<section class="contact py-20 px-6 bg-gray-50"><div class="container mx-auto max-w-xl"><h2 class="text-3xl font-bold text-center mb-8">{{heading}}</h2><form class="space-y-4"><input type="text" placeholder="Your name" class="w-full p-3 border rounded-lg"><input type="email" placeholder="Your email" class="w-full p-3 border rounded-lg"><textarea placeholder="Your message" rows="4" class="w-full p-3 border rounded-lg"></textarea><button type="submit" class="btn-primary w-full py-3 rounded-lg font-semibold">{{cta_text}}</button></form></div></section>',
    },
    {
        "id": "gallery_masonry",
        "type": "gallery",
        "name": "Gallery — Masonry Grid",
        "description": "Responsive image gallery",
        "default_html": '<section class="gallery py-20 px-6"><div class="container mx-auto"><h2 class="text-3xl font-bold text-center mb-12">{{heading}}</h2><div class="columns-2 md:columns-3 gap-4">{{#images}}<img src="{{url}}" alt="{{alt}}" class="rounded-lg mb-4 w-full"/>{{/images}}</div></div></section>',
    },
    {
        "id": "stats_counters",
        "type": "stats",
        "name": "Stats — Counter Row",
        "description": "Key metrics in a row with large numbers",
        "default_html": '<section class="stats py-16 px-6 bg-gray-900 text-white"><div class="container mx-auto"><div class="grid md:grid-cols-4 gap-8 text-center">{{#stats}}<div><div class="text-4xl font-bold mb-2">{{value}}</div><div class="text-gray-400">{{label}}</div></div>{{/stats}}</div></div></section>',
    },
    {
        "id": "footer_standard",
        "type": "footer",
        "name": "Footer — Standard",
        "description": "Multi-column footer with links and copyright",
        "default_html": '<footer class="py-12 px-6 bg-gray-900 text-gray-400"><div class="container mx-auto grid md:grid-cols-4 gap-8"><div><h3 class="text-white font-bold text-lg mb-4">{{company}}</h3><p class="text-sm">{{tagline}}</p></div>{{#columns}}<div><h4 class="text-white font-semibold mb-4">{{title}}</h4><ul class="space-y-2 text-sm">{{#links}}<li><a href="{{url}}" class="hover:text-white transition">{{label}}</a></li>{{/links}}</ul></div>{{/columns}}</div><div class="container mx-auto mt-8 pt-8 border-t border-gray-800 text-sm text-center">© {{year}} {{company}}. All rights reserved.</div></footer>',
    },
    {
        "id": "header_nav",
        "type": "header",
        "name": "Header — Navigation Bar",
        "description": "Top navigation bar with logo and links",
        "default_html": '<header class="py-4 px-6 border-b"><div class="container mx-auto flex items-center justify-between"><a href="/" class="text-xl font-bold">{{logo_text}}</a><nav class="hidden md:flex items-center gap-6">{{#links}}<a href="{{url}}" class="text-gray-600 hover:text-gray-900 transition">{{label}}</a>{{/links}}<a href="#" class="btn-primary px-6 py-2 rounded-lg font-semibold">{{cta_text}}</a></nav></div></header>',
    },
]


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


# ---------------------------------------------------------------------------
# Page CRUD
# ---------------------------------------------------------------------------


async def create_page(db: AsyncSession, data, user) -> Page:
    slug = data.slug or _slugify(data.title)
    page = Page(
        id=uuid.uuid4(),
        title=data.title,
        slug=slug,
        description=data.description,
        style_preset=data.style_preset,
        primary_color=data.primary_color,
        font_family=data.font_family,
        created_by=user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def list_pages(db: AsyncSession, page: int, page_size: int):
    count_q = select(func.count(Page.id))
    total = (await db.execute(count_q)).scalar() or 0

    q = select(Page).order_by(Page.updated_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    pages = result.scalars().all()
    return pages, total


async def get_page(db: AsyncSession, page_id: uuid.UUID) -> Page:
    result = await db.execute(select(Page).where(Page.id == page_id))
    page = result.scalar_one_or_none()
    if page is None:
        raise NotFoundError("Page", str(page_id))
    return page


async def get_page_by_slug(db: AsyncSession, slug: str) -> Page:
    result = await db.execute(
        select(Page).where(Page.slug == slug, Page.status == PageStatus.PUBLISHED)
    )
    page = result.scalar_one_or_none()
    if page is None:
        raise NotFoundError("Page", slug)
    return page


async def update_page(db: AsyncSession, page_id: uuid.UUID, data, user) -> Page:
    page = await get_page(db, page_id)
    update_data = data.model_dump(exclude_unset=True)

    # Create version before update if content changed
    content_fields = {"html_content", "css_content", "js_content", "sections_json"}
    if content_fields & set(update_data.keys()):
        await _create_version(db, page, user.id, "Content updated")

    for field, value in update_data.items():
        if field == "status":
            value = PageStatus(value)
        setattr(page, field, value)

    await db.commit()
    await db.refresh(page)
    return page


async def delete_page(db: AsyncSession, page_id: uuid.UUID) -> None:
    page = await get_page(db, page_id)
    await db.delete(page)
    await db.commit()


async def publish_page(db: AsyncSession, page_id: uuid.UUID, user) -> Page:
    page = await get_page(db, page_id)
    page.status = PageStatus.PUBLISHED
    await _create_version(db, page, user.id, "Published")
    await db.commit()
    await db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


async def _create_version(
    db: AsyncSession, page: Page, user_id: uuid.UUID, summary: str
) -> PageVersion:
    # Get next version number
    q = select(func.max(PageVersion.version_number)).where(
        PageVersion.page_id == page.id
    )
    max_ver = (await db.execute(q)).scalar() or 0
    version = PageVersion(
        id=uuid.uuid4(),
        page_id=page.id,
        version_number=max_ver + 1,
        html_content=page.html_content,
        css_content=page.css_content,
        js_content=page.js_content,
        sections_json=page.sections_json,
        change_summary=summary,
        created_by=user_id,
    )
    db.add(version)
    return version


async def list_versions(db: AsyncSession, page_id: uuid.UUID):
    q = (
        select(PageVersion)
        .where(PageVersion.page_id == page_id)
        .order_by(PageVersion.version_number.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


async def restore_version(
    db: AsyncSession, page_id: uuid.UUID, version_id: uuid.UUID, user
) -> Page:
    page = await get_page(db, page_id)
    result = await db.execute(
        select(PageVersion).where(
            PageVersion.id == version_id, PageVersion.page_id == page_id
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise NotFoundError("PageVersion", str(version_id))

    # Save current as a version before restoring
    await _create_version(db, page, user.id, f"Before restore to v{version.version_number}")

    page.html_content = version.html_content
    page.css_content = version.css_content
    page.js_content = version.js_content
    page.sections_json = version.sections_json
    await db.commit()
    await db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


async def record_page_view(
    db: AsyncSession,
    page_id: uuid.UUID,
    visitor_ip: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
) -> None:
    analytic = PageAnalytic(
        id=uuid.uuid4(),
        page_id=page_id,
        event_type="view",
        visitor_ip=visitor_ip,
        user_agent=user_agent,
        referrer=referrer,
    )
    db.add(analytic)
    await db.commit()


async def record_page_event(
    db: AsyncSession,
    page_id: uuid.UUID,
    event_type: str,
    metadata: dict | None = None,
    visitor_ip: str | None = None,
) -> None:
    analytic = PageAnalytic(
        id=uuid.uuid4(),
        page_id=page_id,
        event_type=event_type,
        visitor_ip=visitor_ip,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(analytic)
    await db.commit()


async def get_page_analytics(
    db: AsyncSession, page_id: uuid.UUID, days: int = 30
) -> dict:
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    from datetime import timedelta

    cutoff = cutoff - timedelta(days=days)

    # Total views
    total_views = (
        await db.execute(
            select(func.count(PageAnalytic.id)).where(
                PageAnalytic.page_id == page_id,
                PageAnalytic.event_type == "view",
                PageAnalytic.created_at >= cutoff,
            )
        )
    ).scalar() or 0

    # Unique visitors (by IP)
    unique_visitors = (
        await db.execute(
            select(func.count(func.distinct(PageAnalytic.visitor_ip))).where(
                PageAnalytic.page_id == page_id,
                PageAnalytic.event_type == "view",
                PageAnalytic.created_at >= cutoff,
            )
        )
    ).scalar() or 0

    # Submissions
    total_submissions = (
        await db.execute(
            select(func.count(PageAnalytic.id)).where(
                PageAnalytic.page_id == page_id,
                PageAnalytic.event_type == "submission",
                PageAnalytic.created_at >= cutoff,
            )
        )
    ).scalar() or 0

    conversion_rate = (
        (total_submissions / total_views * 100) if total_views > 0 else 0.0
    )

    return {
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "total_submissions": total_submissions,
        "conversion_rate": round(conversion_rate, 2),
        "views_by_day": [],
    }


# ---------------------------------------------------------------------------
# AI generation (stub — uses Gemini API when key available)
# ---------------------------------------------------------------------------


async def ai_generate_page(
    db: AsyncSession,
    prompt: str,
    style_preset: str | None = None,
    primary_color: str | None = None,
    font_family: str | None = None,
    sections: list[str] | None = None,
    settings=None,
) -> dict:
    """Generate page HTML using Gemini API (or fallback template)."""
    preset = STYLE_PRESETS.get(style_preset or "modern", STYLE_PRESETS["modern"])
    color = primary_color or preset["preview_colors"]["primary"]
    font = font_family or "Inter, system-ui, sans-serif"

    requested_sections = sections or [
        "header", "hero", "features", "testimonials", "pricing", "faq", "cta", "footer"
    ]

    # Try Gemini API
    gemini_key = getattr(settings, "gemini_api_key", "") if settings else ""
    if gemini_key:
        try:
            return await _generate_with_gemini(
                gemini_key, prompt, color, font, requested_sections
            )
        except Exception:
            pass  # Fallback to template

    # Fallback: assemble from section templates
    html_parts = []
    for section_id in requested_sections:
        template = next(
            (t for t in SECTION_TEMPLATES if t["type"] == section_id), None
        )
        if template:
            html_parts.append(template["default_html"])

    html = "\n".join(html_parts)
    css = _generate_default_css(color, font)

    return {
        "html_content": html,
        "css_content": css,
        "js_content": "",
        "sections_json": json.dumps(requested_sections),
    }


async def ai_refine_page(
    db: AsyncSession,
    page_id: uuid.UUID,
    instruction: str,
    section_index: int | None = None,
    settings=None,
) -> dict:
    """Refine an existing page with AI instruction."""
    page = await get_page(db, page_id)

    gemini_key = getattr(settings, "gemini_api_key", "") if settings else ""
    if gemini_key:
        try:
            return await _refine_with_gemini(
                gemini_key, page.html_content or "", page.css_content or "",
                instruction, section_index,
            )
        except Exception:
            pass

    # If no API key or call fails, return current content unchanged
    return {
        "html_content": page.html_content,
        "css_content": page.css_content,
        "js_content": page.js_content,
        "message": "AI refinement requires a Gemini API key. Content unchanged.",
    }


async def _generate_with_gemini(
    api_key: str,
    prompt: str,
    color: str,
    font: str,
    sections: list[str],
) -> dict:
    """Call Gemini API to generate page HTML/CSS."""
    import httpx

    system_prompt = (
        f"You are a web designer. Generate a complete, responsive landing page "
        f"using HTML and CSS. Use the color {color} as the primary brand color "
        f"and {font} as the font family. Include these sections: {', '.join(sections)}. "
        f"Return ONLY valid HTML in a single code block, with embedded <style> tags. "
        f"Use Tailwind-like utility classes. Make it modern, responsive, and professional."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={
                "contents": [
                    {"parts": [{"text": f"{system_prompt}\n\nUser request: {prompt}"}]}
                ],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Extract HTML and CSS from response
    html = text
    css = ""
    # Try to extract style block
    style_match = re.search(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)
    if style_match:
        css = style_match.group(1).strip()
        html = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL).strip()

    # Strip markdown code fences if present
    html = re.sub(r"^```html?\s*\n?", "", html)
    html = re.sub(r"\n?```\s*$", "", html)

    return {
        "html_content": html,
        "css_content": css,
        "js_content": "",
        "sections_json": json.dumps(sections),
    }


async def _refine_with_gemini(
    api_key: str,
    html: str,
    css: str,
    instruction: str,
    section_index: int | None = None,
) -> dict:
    """Call Gemini API to refine existing page."""
    import httpx

    system_prompt = (
        "You are a web designer. The user has an existing page and wants to refine it. "
        "Apply the user's instruction to the HTML/CSS below. "
        "Return ONLY the complete updated HTML with embedded <style> tags."
    )
    content = f"Current HTML:\n{html}\n\nCurrent CSS:\n{css}\n\nInstruction: {instruction}"
    if section_index is not None:
        content += f"\n\nOnly modify section index {section_index}."

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={
                "contents": [
                    {"parts": [{"text": f"{system_prompt}\n\n{content}"}]}
                ],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

    css_out = ""
    style_match = re.search(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)
    if style_match:
        css_out = style_match.group(1).strip()
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL).strip()

    text = re.sub(r"^```html?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    return {
        "html_content": text,
        "css_content": css_out or css,
        "js_content": "",
    }


def _generate_default_css(color: str, font: str) -> str:
    return f"""
:root {{
  --primary: {color};
  --font-family: {font};
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: var(--font-family); color: #111827; line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.btn-primary {{
  background: var(--primary);
  color: white;
  display: inline-block;
  text-decoration: none;
  transition: opacity 0.2s;
}}
.btn-primary:hover {{ opacity: 0.9; }}
h1, h2, h3 {{ line-height: 1.2; }}
img {{ max-width: 100%; height: auto; }}
@media (max-width: 768px) {{
  .grid {{ grid-template-columns: 1fr !important; }}
  .hidden {{ display: none; }}
}}
"""
