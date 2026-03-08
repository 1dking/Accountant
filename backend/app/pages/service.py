"""Business logic for the AI page builder module."""

import hashlib
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.pages.models import (
    Page, PageAnalytic, PageAnalyticsDaily, PageEvent, PageStatus, PageTemplate,
    PageVersion, PageVisit, TemplateScope, Website,
)

logger = logging.getLogger(__name__)

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
# Website CRUD
# ---------------------------------------------------------------------------


async def create_website(db: AsyncSession, name: str, slug: str | None, user) -> Website:
    ws = Website(
        id=uuid.uuid4(),
        name=name,
        slug=slug or _slugify(name),
        created_by=user.id,
    )
    db.add(ws)
    await db.flush()

    # Create a default Home page
    home = Page(
        id=uuid.uuid4(),
        title="Home",
        slug="home",
        website_id=ws.id,
        page_order=0,
        is_homepage=True,
        created_by=user.id,
    )
    db.add(home)
    await db.commit()
    await db.refresh(ws)
    return ws


async def list_websites(db: AsyncSession):
    q = select(Website).order_by(Website.updated_at.desc())
    result = await db.execute(q)
    websites = result.scalars().all()

    # Attach page counts
    items = []
    for ws in websites:
        count_q = select(func.count(Page.id)).where(Page.website_id == ws.id)
        count = (await db.execute(count_q)).scalar() or 0
        items.append({
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "domain": ws.domain,
            "is_published": ws.is_published,
            "page_count": count,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
        })
    return items


async def get_website(db: AsyncSession, website_id: uuid.UUID) -> Website:
    result = await db.execute(select(Website).where(Website.id == website_id))
    ws = result.scalar_one_or_none()
    if ws is None:
        raise NotFoundError("Website", str(website_id))
    return ws


async def update_website(db: AsyncSession, website_id: uuid.UUID, data) -> Website:
    ws = await get_website(db, website_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ws, field, value)
    await db.commit()
    await db.refresh(ws)
    return ws


async def delete_website(db: AsyncSession, website_id: uuid.UUID) -> None:
    ws = await get_website(db, website_id)
    await db.delete(ws)
    await db.commit()


async def get_website_pages(db: AsyncSession, website_id: uuid.UUID):
    q = select(Page).where(Page.website_id == website_id).order_by(Page.page_order)
    result = await db.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Page CRUD
# ---------------------------------------------------------------------------


async def create_page(db: AsyncSession, data, user) -> Page:
    slug = data.slug or _slugify(data.title)
    page = Page(
        id=uuid.uuid4(),
        title=data.title,
        slug=slug,
        description=getattr(data, "description", None),
        style_preset=getattr(data, "style_preset", None),
        primary_color=getattr(data, "primary_color", None),
        font_family=getattr(data, "font_family", None),
        website_id=getattr(data, "website_id", None),
        page_order=getattr(data, "page_order", 0) or 0,
        created_by=user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def list_pages(db: AsyncSession, page: int, page_size: int, website_id: uuid.UUID | None = None):
    conditions = []
    if website_id:
        conditions.append(Page.website_id == website_id)
    else:
        conditions.append(Page.website_id.is_(None))

    count_q = select(func.count(Page.id))
    if conditions:
        count_q = count_q.where(and_(*conditions))
    total = (await db.execute(count_q)).scalar() or 0

    q = select(Page)
    if conditions:
        q = q.where(and_(*conditions))
    q = q.order_by(Page.updated_at.desc())
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

    await _create_version(db, page, user.id, f"Before restore to v{version.version_number}")

    page.html_content = version.html_content
    page.css_content = version.css_content
    page.js_content = version.js_content
    page.sections_json = version.sections_json
    await db.commit()
    await db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Analytics — legacy (simple counts)
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
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = cutoff - timedelta(days=days)

    total_views = (
        await db.execute(
            select(func.count(PageAnalytic.id)).where(
                PageAnalytic.page_id == page_id,
                PageAnalytic.event_type == "view",
                PageAnalytic.created_at >= cutoff,
            )
        )
    ).scalar() or 0

    unique_visitors = (
        await db.execute(
            select(func.count(func.distinct(PageAnalytic.visitor_ip))).where(
                PageAnalytic.page_id == page_id,
                PageAnalytic.event_type == "view",
                PageAnalytic.created_at >= cutoff,
            )
        )
    ).scalar() or 0

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

    # Views by day from daily table
    daily_q = (
        select(PageAnalyticsDaily)
        .where(PageAnalyticsDaily.page_id == page_id, PageAnalyticsDaily.date >= cutoff.date())
        .order_by(PageAnalyticsDaily.date)
    )
    daily_result = await db.execute(daily_q)
    daily_rows = daily_result.scalars().all()
    views_by_day = [
        {"date": str(r.date), "views": r.page_views, "unique": r.unique_visitors}
        for r in daily_rows
    ]

    # Scroll depth from daily aggregates
    scroll_depth = {}
    if daily_rows:
        s25 = sum(r.scroll_25_count for r in daily_rows)
        s50 = sum(r.scroll_50_count for r in daily_rows)
        s75 = sum(r.scroll_75_count for r in daily_rows)
        s100 = sum(r.scroll_100_count for r in daily_rows)
        total_v = sum(r.page_views for r in daily_rows) or 1
        scroll_depth = {
            "25%": round(s25 / total_v * 100, 1),
            "50%": round(s50 / total_v * 100, 1),
            "75%": round(s75 / total_v * 100, 1),
            "100%": round(s100 / total_v * 100, 1),
        }

    # Top traffic sources from visits
    source_q = (
        select(PageVisit.referrer, func.count(PageVisit.id).label("count"))
        .where(PageVisit.page_id == page_id, PageVisit.created_at >= cutoff)
        .group_by(PageVisit.referrer)
        .order_by(func.count(PageVisit.id).desc())
        .limit(10)
    )
    source_result = await db.execute(source_q)
    top_sources = [
        {"source": r[0] or "Direct", "count": r[1]}
        for r in source_result.all()
    ]

    # Devices
    device_q = (
        select(PageVisit.device_type, func.count(PageVisit.id).label("count"))
        .where(PageVisit.page_id == page_id, PageVisit.created_at >= cutoff)
        .group_by(PageVisit.device_type)
    )
    device_result = await db.execute(device_q)
    devices = {r[0] or "Unknown": r[1] for r in device_result.all()}

    # Top clicks
    click_q = (
        select(PageEvent.event_data_json, func.count(PageEvent.id).label("count"))
        .where(
            PageEvent.page_id == page_id,
            PageEvent.event_type == "click",
            PageEvent.created_at >= cutoff,
        )
        .group_by(PageEvent.event_data_json)
        .order_by(func.count(PageEvent.id).desc())
        .limit(20)
    )
    click_result = await db.execute(click_q)
    top_clicks = []
    for r in click_result.all():
        try:
            data = json.loads(r[0]) if r[0] else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        top_clicks.append({"element": data.get("text", data.get("selector", "Unknown")), "count": r[1]})

    # UTM campaigns
    utm_q = (
        select(
            PageVisit.utm_campaign,
            func.count(PageVisit.id).label("visitors"),
        )
        .where(
            PageVisit.page_id == page_id,
            PageVisit.created_at >= cutoff,
            PageVisit.utm_campaign.isnot(None),
        )
        .group_by(PageVisit.utm_campaign)
        .order_by(func.count(PageVisit.id).desc())
        .limit(10)
    )
    utm_result = await db.execute(utm_q)
    utm_campaigns = [{"campaign": r[0], "visitors": r[1]} for r in utm_result.all()]

    avg_time = 0
    bounce_rate = 0.0
    if daily_rows:
        total_time = sum(r.avg_time_seconds * r.page_views for r in daily_rows)
        total_pv = sum(r.page_views for r in daily_rows) or 1
        avg_time = round(total_time / total_pv)
        total_bounce = sum(r.bounce_count for r in daily_rows)
        bounce_rate = round(total_bounce / total_pv * 100, 1)

    return {
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "total_submissions": total_submissions,
        "conversion_rate": round(conversion_rate, 2),
        "views_by_day": views_by_day,
        "avg_time_seconds": avg_time,
        "bounce_rate": bounce_rate,
        "top_sources": top_sources,
        "devices": devices,
        "scroll_depth": scroll_depth,
        "top_clicks": top_clicks,
        "utm_campaigns": utm_campaigns,
    }


# ---------------------------------------------------------------------------
# Analytics — detailed tracking (new visitor-level system)
# ---------------------------------------------------------------------------


def _parse_user_agent(ua_string: str | None) -> dict:
    """Basic UA parsing."""
    if not ua_string:
        return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}

    ua = ua_string.lower()
    device = "desktop"
    if "mobile" in ua or "android" in ua and "tablet" not in ua:
        device = "mobile"
    elif "tablet" in ua or "ipad" in ua:
        device = "tablet"

    browser = "other"
    for b in ["chrome", "firefox", "safari", "edge", "opera"]:
        if b in ua:
            browser = b.title()
            break

    os_name = "other"
    for o, n in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux"),
                  ("android", "Android"), ("iphone", "iOS"), ("ipad", "iOS")]:
        if o in ua:
            os_name = n
            break

    return {"device_type": device, "browser": browser, "os": os_name}


async def track_event(
    db: AsyncSession,
    page_id: uuid.UUID,
    visitor_id: str,
    session_id: str,
    event_type: str,
    event_data: dict | None = None,
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> None:
    """Track a visitor event (page_view, scroll, click, etc.)."""
    # Get or create visit
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16] if client_ip else None

    # Check for existing visit in this session
    visit_q = select(PageVisit).where(
        PageVisit.page_id == page_id,
        PageVisit.session_id == session_id,
        PageVisit.visitor_id == visitor_id,
    )
    visit_result = await db.execute(visit_q)
    visit = visit_result.scalar_one_or_none()

    if not visit:
        ua_info = _parse_user_agent(user_agent)
        # Get website_id from page
        page = await db.execute(select(Page.website_id).where(Page.id == page_id))
        ws_id = page.scalar_one_or_none()

        visit = PageVisit(
            id=uuid.uuid4(),
            page_id=page_id,
            website_id=ws_id,
            visitor_id=visitor_id,
            session_id=session_id,
            referrer=referrer,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            device_type=ua_info["device_type"],
            browser=ua_info["browser"],
            os=ua_info["os"],
            ip_hash=ip_hash,
        )
        db.add(visit)
        await db.flush()

    # Record the event
    evt = PageEvent(
        id=uuid.uuid4(),
        visit_id=visit.id,
        page_id=page_id,
        event_type=event_type,
        event_data_json=json.dumps(event_data) if event_data else None,
    )
    db.add(evt)
    await db.commit()


async def aggregate_daily_analytics(db: AsyncSession) -> int:
    """Aggregate yesterday's page_visits/events into page_analytics_daily."""
    yesterday = date.today() - timedelta(days=1)
    logger.info("Aggregating analytics for %s", yesterday)

    # Get all pages that had visits yesterday
    page_ids_q = (
        select(func.distinct(PageVisit.page_id))
        .where(func.date(PageVisit.created_at) == yesterday)
    )
    page_ids_result = await db.execute(page_ids_q)
    page_ids = [r[0] for r in page_ids_result.all()]

    count = 0
    for pid in page_ids:
        # Delete existing row for this date
        await db.execute(
            delete(PageAnalyticsDaily).where(
                PageAnalyticsDaily.page_id == pid,
                PageAnalyticsDaily.date == yesterday,
            )
        )

        # Count visits
        visitors = (await db.execute(
            select(func.count(PageVisit.id)).where(
                PageVisit.page_id == pid,
                func.date(PageVisit.created_at) == yesterday,
            )
        )).scalar() or 0

        unique = (await db.execute(
            select(func.count(func.distinct(PageVisit.visitor_id))).where(
                PageVisit.page_id == pid,
                func.date(PageVisit.created_at) == yesterday,
            )
        )).scalar() or 0

        # Count events
        def _count_event(event_type):
            return select(func.count(PageEvent.id)).where(
                PageEvent.page_id == pid,
                PageEvent.event_type == event_type,
                func.date(PageEvent.created_at) == yesterday,
            )

        page_views = (await db.execute(_count_event("page_view"))).scalar() or visitors
        s25 = (await db.execute(_count_event("scroll_25"))).scalar() or 0
        s50 = (await db.execute(_count_event("scroll_50"))).scalar() or 0
        s75 = (await db.execute(_count_event("scroll_75"))).scalar() or 0
        s100 = (await db.execute(_count_event("scroll_100"))).scalar() or 0
        clicks = (await db.execute(_count_event("click"))).scalar() or 0
        forms = (await db.execute(_count_event("form_submit"))).scalar() or 0

        # Time on page (from time_on_page events)
        time_q = select(PageEvent.event_data_json).where(
            PageEvent.page_id == pid,
            PageEvent.event_type == "time_on_page",
            func.date(PageEvent.created_at) == yesterday,
        )
        time_result = await db.execute(time_q)
        total_time = 0
        time_count = 0
        for r in time_result.scalars().all():
            try:
                d = json.loads(r) if r else {}
                total_time += d.get("seconds", 0)
                time_count += 1
            except (json.JSONDecodeError, TypeError):
                pass
        avg_time = round(total_time / time_count) if time_count else 0

        # Bounce = visits with only 1 event (page_view only)
        bounce_q = select(func.count()).select_from(
            select(PageEvent.visit_id)
            .where(
                PageEvent.page_id == pid,
                func.date(PageEvent.created_at) == yesterday,
            )
            .group_by(PageEvent.visit_id)
            .having(func.count(PageEvent.id) == 1)
            .subquery()
        )
        bounces = (await db.execute(bounce_q)).scalar() or 0

        daily = PageAnalyticsDaily(
            id=uuid.uuid4(),
            page_id=pid,
            date=yesterday,
            visitors=visitors,
            unique_visitors=unique,
            page_views=page_views,
            avg_time_seconds=avg_time,
            bounce_count=bounces,
            scroll_25_count=s25,
            scroll_50_count=s50,
            scroll_75_count=s75,
            scroll_100_count=s100,
            click_count=clicks,
            form_submit_count=forms,
        )
        db.add(daily)
        count += 1

    await db.commit()
    logger.info("Aggregated analytics for %d pages", count)
    return count


# ---------------------------------------------------------------------------
# Page Templates CRUD
# ---------------------------------------------------------------------------


async def list_templates(
    db: AsyncSession,
    include_platform: bool = True,
) -> list[PageTemplate]:
    """List all active templates (org + platform)."""
    q = select(PageTemplate).where(PageTemplate.is_active == True)
    if not include_platform:
        q = q.where(PageTemplate.scope == TemplateScope.ORG)
    q = q.order_by(PageTemplate.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> PageTemplate:
    result = await db.execute(
        select(PageTemplate).where(PageTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise NotFoundError("Template not found")
    return t


async def create_template(
    db: AsyncSession,
    name: str,
    description: str | None,
    category_industry: str | None,
    category_type: str | None,
    html_content: str | None,
    css_content: str | None,
    metadata_json: str | None,
    scope: str,
    created_by: uuid.UUID | None,
) -> PageTemplate:
    t = PageTemplate(
        id=uuid.uuid4(),
        name=name,
        description=description,
        category_industry=category_industry,
        category_type=category_type,
        html_content=html_content,
        css_content=css_content,
        metadata_json=metadata_json,
        scope=TemplateScope(scope) if scope else TemplateScope.ORG,
        created_by=created_by,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def create_template_from_page(
    db: AsyncSession,
    page_id: uuid.UUID,
    name: str,
    description: str | None,
    category_industry: str | None,
    category_type: str | None,
    scope: str,
    created_by: uuid.UUID,
) -> PageTemplate:
    """Create a template from an existing page's content."""
    page = await get_page(db, page_id)
    return await create_template(
        db,
        name=name,
        description=description,
        category_industry=category_industry,
        category_type=category_type,
        html_content=page.html_content,
        css_content=page.css_content,
        metadata_json=json.dumps({
            "source_page_id": str(page_id),
            "style_preset": page.style_preset,
            "primary_color": page.primary_color,
            "font_family": page.font_family,
        }),
        scope=scope,
        created_by=created_by,
    )


async def update_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    data: dict,
) -> PageTemplate:
    t = await get_template(db, template_id)
    for key, val in data.items():
        if val is not None and hasattr(t, key):
            if key == "scope":
                setattr(t, key, TemplateScope(val))
            else:
                setattr(t, key, val)
    await db.commit()
    await db.refresh(t)
    return t


async def delete_template(db: AsyncSession, template_id: uuid.UUID) -> None:
    t = await get_template(db, template_id)
    await db.delete(t)
    await db.commit()


async def create_page_from_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    title: str,
    user,
    website_id: uuid.UUID | None = None,
    org_name: str | None = None,
) -> Page:
    """Create a new page using a template's content, with auto-branding replacement."""
    t = await get_template(db, template_id)
    html = t.html_content or ""
    css = t.css_content or ""

    # Load org branding for auto-replacement
    brand_name = org_name or ""
    brand_phone = ""
    brand_email = ""
    brand_color = ""
    brand_logo = ""
    try:
        from app.settings.models import CompanySetting
        result = await db.execute(select(CompanySetting).limit(1))
        company = result.scalar_one_or_none()
        if company:
            brand_name = brand_name or getattr(company, "company_name", "") or ""
            brand_phone = getattr(company, "phone", "") or ""
            brand_email = getattr(company, "email", "") or ""
            brand_color = getattr(company, "primary_color", "") or ""
            brand_logo = getattr(company, "logo_url", "") or ""
    except Exception:
        pass

    # Auto-replace placeholder branding
    if brand_name:
        for placeholder in [
            "{{company_name}}", "{{org_name}}", "Company Name",
            "Your Company", "YourBrand", "[Business Name]",
        ]:
            html = html.replace(placeholder, brand_name)
            css = css.replace(placeholder, brand_name)

    if brand_phone:
        for placeholder in [
            "{{phone}}", "(555) 123-4567", "+1 (555) 123-4567",
            "555-123-4567",
        ]:
            html = html.replace(placeholder, brand_phone)

    if brand_email:
        for placeholder in [
            "{{email}}", "hello@example.com", "info@example.com",
            "contact@example.com",
        ]:
            html = html.replace(placeholder, brand_email)

    if brand_color:
        html = html.replace("{{brand_color}}", brand_color)

    if brand_logo:
        html = html.replace("{{logo_url}}", brand_logo)

    from app.pages.schemas import PageCreate
    page_data = PageCreate(
        title=title,
        website_id=website_id,
    )
    page = await create_page(db, page_data, user)
    page.html_content = html
    page.css_content = css
    await db.commit()
    await db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# AI generation
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
            pass

    # Try Claude API
    anthropic_key = getattr(settings, "anthropic_api_key", "") if settings else ""
    if anthropic_key:
        try:
            return await _generate_with_claude(
                anthropic_key, prompt, color, font, requested_sections
            )
        except Exception:
            pass

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

    anthropic_key = getattr(settings, "anthropic_api_key", "") if settings else ""
    if anthropic_key:
        try:
            return await _refine_with_claude(
                anthropic_key, page.html_content or "", page.css_content or "",
                instruction, section_index,
            )
        except Exception:
            pass

    return {
        "html_content": page.html_content,
        "css_content": page.css_content,
        "js_content": page.js_content,
        "message": "AI refinement requires a Gemini or Anthropic API key. Content unchanged.",
    }


async def ai_chat_generate(
    db: AsyncSession,
    page_id: uuid.UUID,
    message: str,
    settings=None,
) -> dict:
    """Chat-style page generation/refinement. Returns updated HTML/CSS and AI response."""
    page = await get_page(db, page_id)

    # Load chat history
    chat_history = []
    if page.chat_history_json:
        try:
            chat_history = json.loads(page.chat_history_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Add user message
    chat_history.append({"role": "user", "content": message})

    gemini_key = getattr(settings, "gemini_api_key", "") if settings else ""
    anthropic_key = getattr(settings, "anthropic_api_key", "") if settings else ""

    # Build context with branding info
    branding_context = ""
    try:
        from app.settings.models import CompanySetting
        result = await db.execute(select(CompanySetting).limit(1))
        company = result.scalar_one_or_none()
        if company:
            branding_context = f"\nCompany: {company.company_name or ''}"
    except Exception:
        pass

    primary_color = page.primary_color or "#2563eb"
    font_family = page.font_family or "Inter, system-ui, sans-serif"
    current_html = page.html_content or ""
    current_css = page.css_content or ""
    is_new_page = not current_html.strip()

    # Build page state section (avoid backslashes in f-string expressions for Python <3.12)
    nl = "\n"
    if is_new_page:
        page_state_section = "This is a NEW page — generate a complete website from scratch."
    else:
        page_state_section = "Current HTML (modify this):" + nl + current_html[:3000]
    if current_css.strip():
        page_state_section += nl + nl + "Current CSS:" + nl + current_css[:1000]

    system_prompt = (
        "You are an elite web designer who creates Apple-level, award-winning websites.\n"
        "You produce COMPLETE, standalone HTML files that look like they cost $50,000 to build.\n"
        + branding_context + "\n\n"
        "## DESIGN STANDARDS (MANDATORY)\n"
        "Every page you create MUST have:\n\n"
        "1. **COMPLETE STANDALONE HTML** — Return a FULL HTML document with <!DOCTYPE html>, <head>, and <body>.\n"
        "   Include ALL resources in the HTML file via CDN links:\n"
        "   - Tailwind CSS: <script src=\"https://cdn.tailwindcss.com\"></script>\n"
        "   - Google Fonts: <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap\" rel=\"stylesheet\">\n"
        "   - Lucide Icons: <script src=\"https://unpkg.com/lucide@latest/dist/umd/lucide.js\"></script> then <script>lucide.createIcons();</script> before </body>\n\n"
        "2. **REAL IMAGES FROM UNSPLASH** — NEVER use placeholder boxes or gray divs.\n"
        "   Use real, high-quality images from Unsplash:\n"
        "   - Hero backgrounds: <img src=\"https://images.unsplash.com/photo-[ID]?w=1920&q=80\" />\n"
        "   - Team photos: Use portrait photos from Unsplash\n"
        "   - Service images: Use relevant industry photos\n"
        "   - Pick images that match the business type (dental=smiling patients, restaurant=food, etc.)\n"
        "   - Always include alt text and loading=\"lazy\" on images below the fold\n\n"
        "3. **PREMIUM VISUAL DESIGN** — Every page must include:\n"
        "   - Glassmorphism effects: backdrop-blur-xl, bg-white/10, border border-white/20\n"
        "   - Smooth gradients: bg-gradient-to-br, from-[color]-900 via-[color]-800 to-[color]-700\n"
        "   - Subtle animations: CSS transitions, hover transforms (scale, translateY), fade-in on scroll\n"
        "   - Shadow depth: shadow-2xl, shadow-[color]/20 for colored shadows\n"
        "   - Rounded corners: rounded-2xl or rounded-3xl for cards\n"
        "   - Generous whitespace: py-24 or py-32 between sections\n"
        "   - Typography hierarchy: text-5xl/text-6xl bold headings, text-lg/text-xl light subheadings\n"
        "   - Dark overlays on hero images: bg-black/40 or bg-gradient-to-r from-black/60\n"
        "   - Floating cards with glass effect for testimonials and features\n"
        "   - Accent color pops: " + primary_color + " for CTAs, highlights, and decorative elements\n\n"
        "4. **RESPONSIVE DESIGN** — Must work on desktop, tablet, and mobile:\n"
        "   - Use Tailwind responsive prefixes: sm:, md:, lg:, xl:\n"
        "   - Mobile-first grid: grid-cols-1 md:grid-cols-2 lg:grid-cols-3\n"
        "   - Hamburger menu concept for mobile (can be CSS-only)\n\n"
        "5. **PROFESSIONAL SECTIONS** — Include these patterns:\n"
        "   - Navigation: Sticky, transparent on scroll, glass effect\n"
        "   - Hero: Full-viewport height, dramatic imagery, compelling headline, CTA button\n"
        "   - Social proof: Client logos, testimonial cards with photos, star ratings\n"
        "   - Services/Features: Icon cards with hover effects, 3-column grid\n"
        "   - About: Split layout with image + text, company story\n"
        "   - CTA: Bold section with gradient background and centered button\n"
        "   - Footer: Multi-column with links, contact info, social icons, copyright\n\n"
        "6. **MICRO-INTERACTIONS** — Add CSS-only animations:\n"
        "   - Buttons: hover:scale-105 hover:shadow-lg transition-all duration-300\n"
        "   - Cards: hover:-translate-y-2 hover:shadow-2xl transition-all duration-500\n"
        "   - Links: hover:text-[accent] transition-colors\n"
        "   - Add scroll-based fade-in using IntersectionObserver in a <script> tag\n\n"
        "7. **COLOR PALETTE** — Use " + primary_color + " as the accent. Build a cohesive palette:\n"
        "   - Dark backgrounds: slate-900, gray-950, or deep brand color\n"
        "   - Light text on dark: white, gray-100, gray-200\n"
        "   - Accent highlights: " + primary_color + " for buttons and key elements\n"
        "   - Subtle borders: border-white/10 or border-gray-200\n\n"
        "## CURRENT PAGE STATE\n"
        + page_state_section + "\n\n"
        "## RESPONSE FORMAT\n"
        "Return your response as JSON with this EXACT structure:\n"
        '{"response": "Brief conversational summary of what you built/changed (2-3 sentences, NO code)", '
        '"html_content": "The COMPLETE standalone HTML document with <!DOCTYPE html> through </html>", '
        '"css_content": ""}\n\n'
        "CRITICAL RULES:\n"
        "- html_content MUST be a complete HTML document (<!DOCTYPE html> to </html>)\n"
        "- Put ALL CSS inside <style> tags within the HTML <head> — do NOT put CSS in css_content\n"
        "- css_content should be empty string (all styles go in the HTML)\n"
        "- The response field must contain ONLY conversational text — NEVER include HTML code in it\n"
        "- Always return the FULL HTML, not just changed parts\n"
        "- Use font: " + font_family + "\n"
        "- Primary accent color: " + primary_color
    )

    # Load reference designs for new page generation or major changes
    image_parts: list[dict] = []
    reference_text = ""
    if is_new_page or any(w in message.lower() for w in [
        "create", "build", "make", "design", "generate", "new", "redesign", "rebuild",
    ]):
        try:
            from app.pages.references import build_reference_parts
            image_parts, reference_text = build_reference_parts(message)
            logger.info("Loaded %d reference images for prompt", len(image_parts))
        except Exception as e:
            logger.warning("Failed to load reference designs: %s", e)

    result = None

    if gemini_key:
        try:
            result = await _chat_with_gemini(
                gemini_key, system_prompt, chat_history,
                image_parts=image_parts, reference_text=reference_text,
            )
        except Exception as e:
            logger.warning("Gemini chat failed: %s", e)

    if not result and anthropic_key:
        try:
            result = await _chat_with_claude(anthropic_key, system_prompt, chat_history)
        except Exception as e:
            logger.warning("Claude chat failed: %s", e)

    if not result:
        result = {
            "response": "I need an AI API key (Gemini or Anthropic) to generate pages. Please configure one in settings.",
            "html_content": page.html_content or "",
            "css_content": page.css_content or "",
        }

    # Save chat history
    chat_history.append({"role": "assistant", "content": result["response"]})
    # Keep last 50 messages
    if len(chat_history) > 50:
        chat_history = chat_history[-50:]
    page.chat_history_json = json.dumps(chat_history)

    # Update page content if AI returned new content
    if result.get("html_content") and result["html_content"] != page.html_content:
        page.html_content = result["html_content"]
    if result.get("css_content") and result["css_content"] != page.css_content:
        page.css_content = result["css_content"]

    await db.commit()
    await db.refresh(page)

    return {
        "response": result["response"],
        "html_content": page.html_content,
        "css_content": page.css_content,
        "js_content": page.js_content or "",
    }


async def _chat_with_gemini(
    api_key: str,
    system_prompt: str,
    chat_history: list,
    image_parts: list[dict] | None = None,
    reference_text: str = "",
) -> dict:
    import httpx

    # Build multimodal parts: system prompt + optional reference images + reference text + chat
    parts: list[dict] = [{"text": system_prompt}]

    # Add reference images (screenshots of premium designs)
    if image_parts:
        for img_part in image_parts:
            parts.append(img_part)

    # Add reference text (code + instructions to match quality)
    if reference_text:
        parts.append({"text": reference_text})

    # Add chat history
    for msg in chat_history[-10:]:  # Last 10 messages for context
        parts.append({"text": msg["role"].upper() + ": " + msg["content"]})

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            + "?key=" + api_key,
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 65536,
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

    return _parse_ai_response(text)


async def _chat_with_claude(api_key: str, system_prompt: str, chat_history: list) -> dict:
    import httpx

    messages = []
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 16384,
                "system": system_prompt,
                "messages": messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]

    return _parse_ai_response(text)


def _parse_ai_response(text: str) -> dict:
    """Parse AI response — try JSON first, then extract HTML/CSS."""
    # Try JSON parse
    try:
        # Direct JSON parse (for responseMimeType=application/json)
        parsed = json.loads(text)
        if "response" in parsed and "html_content" in parsed:
            return {
                "response": parsed["response"],
                "html_content": parsed.get("html_content", ""),
                "css_content": parsed.get("css_content", ""),
            }
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        # Find JSON block in mixed text
        json_match = re.search(r'\{[\s\S]*"response"[\s\S]*"html_content"[\s\S]*\}', text)
        if json_match:
            parsed = json.loads(json_match.group())
            if "response" in parsed:
                return {
                    "response": parsed["response"],
                    "html_content": parsed.get("html_content", ""),
                    "css_content": parsed.get("css_content", ""),
                }
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: extract HTML and CSS from fenced blocks
    html = ""
    css = ""
    response = text

    html_match = re.search(r'```html\s*\n?([\s\S]*?)\n?```', text)
    if html_match:
        html = html_match.group(1).strip()
        response = re.sub(r'```html[\s\S]*?```', '', text).strip()

    # Check for full HTML document without fences
    if not html:
        doc_match = re.search(r'(<!DOCTYPE html[\s\S]*</html>)', text, re.IGNORECASE)
        if doc_match:
            html = doc_match.group(1).strip()
            response = text[:doc_match.start()].strip()

    css_match = re.search(r'```css\s*\n?([\s\S]*?)\n?```', text)
    if css_match:
        css = css_match.group(1).strip()
        response = re.sub(r'```css[\s\S]*?```', '', response).strip()

    # Clean up response — remove any remaining code fences or HTML tags
    response = re.sub(r'```[\s\S]*?```', '', response).strip()
    response = re.sub(r'<[^>]+>', '', response).strip()

    # If the html is a full document, do NOT extract styles separately
    # (styles belong in the document <head>)
    if html and not html.strip().lower().startswith("<!doctype") and not html.strip().lower().startswith("<html"):
        # Only extract embedded styles for partial HTML
        if not css:
            style_match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
            if style_match:
                css = style_match.group(1).strip()
                html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL).strip()

    return {
        "response": response or "I've updated the page.",
        "html_content": html,
        "css_content": css,
    }


async def _generate_with_gemini(
    api_key: str, prompt: str, color: str, font: str, sections: list[str],
) -> dict:
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

    html = text
    css = ""
    style_match = re.search(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)
    if style_match:
        css = style_match.group(1).strip()
        html = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL).strip()

    html = re.sub(r"^```html?\s*\n?", "", html)
    html = re.sub(r"\n?```\s*$", "", html)

    return {
        "html_content": html,
        "css_content": css,
        "js_content": "",
        "sections_json": json.dumps(sections),
    }


async def _generate_with_claude(
    api_key: str, prompt: str, color: str, font: str, sections: list[str],
) -> dict:
    import httpx

    system_prompt = (
        f"You are a web designer. Generate a complete, responsive landing page "
        f"using HTML and CSS. Use {color} as primary color and {font} as font. "
        f"Include sections: {', '.join(sections)}. "
        f"Return ONLY the HTML with embedded <style> tags. Modern, responsive, professional."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": f"{system_prompt}\n\n{prompt}"}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]

    html = text
    css = ""
    style_match = re.search(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)
    if style_match:
        css = style_match.group(1).strip()
        html = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL).strip()

    html = re.sub(r"^```html?\s*\n?", "", html)
    html = re.sub(r"\n?```\s*$", "", html)

    return {
        "html_content": html,
        "css_content": css,
        "js_content": "",
        "sections_json": json.dumps(sections),
    }


async def _refine_with_gemini(
    api_key: str, html: str, css: str, instruction: str, section_index: int | None = None,
) -> dict:
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


async def _refine_with_claude(
    api_key: str, html: str, css: str, instruction: str, section_index: int | None = None,
) -> dict:
    import httpx

    system_prompt = (
        "You are a web designer. Apply the instruction to the HTML/CSS. "
        "Return the complete updated HTML with embedded <style> tags."
    )
    content = f"HTML:\n{html}\n\nCSS:\n{css}\n\nInstruction: {instruction}"
    if section_index is not None:
        content += f"\n\nOnly modify section index {section_index}."

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": f"{system_prompt}\n\n{content}"}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]

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


# ---------------------------------------------------------------------------
# Video processing
# ---------------------------------------------------------------------------


async def process_video(input_path: str, output_dir: str) -> dict:
    """Process uploaded video: compress, strip audio, generate poster."""
    import asyncio
    import os

    base_name = str(uuid.uuid4())
    mp4_path = os.path.join(output_dir, f"{base_name}.mp4")
    webm_path = os.path.join(output_dir, f"{base_name}.webm")
    poster_path = os.path.join(output_dir, f"{base_name}_poster.jpg")

    os.makedirs(output_dir, exist_ok=True)

    # Generate poster (first frame)
    poster_cmd = [
        "ffmpeg", "-i", input_path, "-vframes", "1", "-q:v", "2",
        "-y", poster_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *poster_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Compress to MP4 (H.264, 720p, no audio, max 30s)
    mp4_cmd = [
        "ffmpeg", "-i", input_path, "-an", "-vf", "scale=-2:720",
        "-c:v", "libx264", "-preset", "medium", "-crf", "28",
        "-t", "30", "-movflags", "+faststart", "-y", mp4_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *mp4_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Compress to WebM (VP9, 720p, no audio, max 30s)
    webm_cmd = [
        "ffmpeg", "-i", input_path, "-an", "-vf", "scale=-2:720",
        "-c:v", "libvpx-vp9", "-b:v", "1M", "-crf", "35",
        "-t", "30", "-y", webm_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *webm_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Get duration
    duration = 0.0
    try:
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", input_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        duration = min(float(stdout.decode().strip()), 30.0)
    except Exception:
        pass

    # Clean up input
    try:
        os.unlink(input_path)
    except Exception:
        pass

    return {
        "mp4_path": mp4_path,
        "webm_path": webm_path,
        "poster_path": poster_path,
        "duration_seconds": duration,
    }


# ---------------------------------------------------------------------------
# Tracking pixel / script injection
# ---------------------------------------------------------------------------


def build_tracking_head(page: Page, website: Website | None = None) -> str:
    """Build tracking pixel/script tags to inject in <head>."""
    scripts = []

    # Merge website-level + page-level pixels (page overrides)
    pixels = {}
    if website and website.tracking_pixels_json:
        try:
            pixels.update(json.loads(website.tracking_pixels_json))
        except (json.JSONDecodeError, TypeError):
            pass
    if page.tracking_pixels_json:
        try:
            page_pixels = json.loads(page.tracking_pixels_json)
            pixels.update(page_pixels)
        except (json.JSONDecodeError, TypeError):
            pass

    # Facebook Pixel
    fb_id = pixels.get("facebook_pixel")
    if fb_id:
        scripts.append(
            f"<script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?"
            f"n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;"
            f"n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;"
            f"t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}"
            f"(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');"
            f"fbq('init','{fb_id}');fbq('track','PageView');</script>"
        )

    # GA4
    ga4_id = pixels.get("ga4")
    if ga4_id:
        scripts.append(
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>'
            f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
            f"gtag('js',new Date());gtag('config','{ga4_id}');</script>"
        )

    # GTM
    gtm_id = pixels.get("gtm")
    if gtm_id:
        scripts.append(
            f"<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),"
            f"event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?"
            f"'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;"
            f"f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','{gtm_id}');</script>"
        )

    # TikTok Pixel
    tt_id = pixels.get("tiktok")
    if tt_id:
        scripts.append(
            f"<script>!function(w,d,t){{w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];"
            f"ttq.methods=['page','track','identify','instances','debug','on','off','once','ready','alias','group','enableCookie','disableCookie'];"
            f"ttq.setAndDefer=function(t,e){{t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}};"
            f"for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);"
            f"ttq.instance=function(t){{for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);"
            f"return e}};ttq.load=function(e,n){{var i='https://analytics.tiktok.com/i18n/pixel/events.js';"
            f"ttq._i=ttq._i||{{}};ttq._i[e]=[];ttq._i[e]._u=i;ttq._t=ttq._t||{{}};ttq._t[e]=+new Date;"
            f"ttq._o=ttq._o||{{}};ttq._o[e]=n||{{}};var o=document.createElement('script');"
            f"o.type='text/javascript';o.async=!0;o.src=i+'?sdkid='+e+'&lib='+t;var a=document.getElementsByTagName('script')[0];"
            f"a.parentNode.insertBefore(o,a)}};ttq.load('{tt_id}');ttq.page();}}(window,document,'ttq');</script>"
        )

    # LinkedIn
    li_id = pixels.get("linkedin")
    if li_id:
        scripts.append(
            f'<script>_linkedin_partner_id="{li_id}";window._linkedin_data_partner_ids='
            f'window._linkedin_data_partner_ids||[];window._linkedin_data_partner_ids.push(_linkedin_partner_id);</script>'
            f'<script>(function(l){{if(!l){{window.lintrk=function(a,b){{window.lintrk.q.push([a,b])}};'
            f'window.lintrk.q=[]}};var s=document.getElementsByTagName("script")[0];var b=document.createElement("script");'
            f'b.type="text/javascript";b.async=true;b.src="https://snap.licdn.com/li.lms-analytics/insight.min.js";'
            f's.parentNode.insertBefore(b,s);}})(window.lintrk);</script>'
        )

    # Custom scripts (head placement)
    custom_scripts = pixels.get("custom_scripts", [])
    for script in custom_scripts:
        if script.get("active") and script.get("placement") == "head":
            scripts.append(script.get("code", ""))

    return "\n".join(scripts)


def build_tracking_body_start(page: Page, website: Website | None = None) -> str:
    """Build scripts for body start."""
    pixels = {}
    if website and website.tracking_pixels_json:
        try:
            pixels.update(json.loads(website.tracking_pixels_json))
        except (json.JSONDecodeError, TypeError):
            pass
    if page.tracking_pixels_json:
        try:
            pixels.update(json.loads(page.tracking_pixels_json))
        except (json.JSONDecodeError, TypeError):
            pass

    scripts = []
    custom_scripts = pixels.get("custom_scripts", [])
    for script in custom_scripts:
        if script.get("active") and script.get("placement") == "body_start":
            scripts.append(script.get("code", ""))
    return "\n".join(scripts)


def build_tracking_body_end(page: Page, website: Website | None = None) -> str:
    """Build scripts for body end."""
    pixels = {}
    if website and website.tracking_pixels_json:
        try:
            pixels.update(json.loads(website.tracking_pixels_json))
        except (json.JSONDecodeError, TypeError):
            pass
    if page.tracking_pixels_json:
        try:
            pixels.update(json.loads(page.tracking_pixels_json))
        except (json.JSONDecodeError, TypeError):
            pass

    scripts = []
    custom_scripts = pixels.get("custom_scripts", [])
    for script in custom_scripts:
        if script.get("active") and script.get("placement") == "body_end":
            scripts.append(script.get("code", ""))
    return "\n".join(scripts)


def build_analytics_script(page_id: str, base_url: str) -> str:
    """Build the lightweight analytics tracking script."""
    return f"""<script>
(function(){{
  var pid="{page_id}";
  var endpoint="{base_url}/api/analytics/track";
  var vid=localStorage.getItem("_av")||("v_"+Math.random().toString(36).substr(2,9));
  localStorage.setItem("_av",vid);
  var sid=sessionStorage.getItem("_as")||("s_"+Math.random().toString(36).substr(2,9));
  sessionStorage.setItem("_as",sid);
  var u=new URL(location.href);
  var utm_s=u.searchParams.get("utm_source");
  var utm_m=u.searchParams.get("utm_medium");
  var utm_c=u.searchParams.get("utm_campaign");
  function send(type,data){{
    var body=JSON.stringify({{page_id:pid,visitor_id:vid,session_id:sid,event_type:type,event_data:data||{{}},referrer:document.referrer,utm_source:utm_s,utm_medium:utm_m,utm_campaign:utm_c}});
    if(navigator.sendBeacon){{navigator.sendBeacon(endpoint,body)}}
    else{{fetch(endpoint,{{method:"POST",body:body,headers:{{"Content-Type":"application/json"}},keepalive:true}})}}
  }}
  send("page_view");
  var scrolled={{}};
  window.addEventListener("scroll",function(){{
    var pct=Math.round((window.scrollY+window.innerHeight)/document.documentElement.scrollHeight*100);
    [25,50,75,100].forEach(function(t){{if(pct>=t&&!scrolled[t]){{scrolled[t]=1;send("scroll_"+t)}}}});
  }});
  document.addEventListener("click",function(e){{
    var t=e.target.closest("a,button,[role=button]");
    if(t){{send("click",{{text:t.innerText.substring(0,100),selector:t.tagName+(t.className?" ."+t.className.split(" ")[0]:""),href:t.href||""}})}}
  }});
  var start=Date.now();
  window.addEventListener("beforeunload",function(){{send("time_on_page",{{seconds:Math.round((Date.now()-start)/1000)}})}});
}})();
</script>"""
