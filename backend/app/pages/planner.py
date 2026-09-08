"""AI site planner — copy-only (block model v2, S4).

"Build me a site" never produces markup. The AI:
  1. PLAN  — picks blocks from the library catalogue (variant ids only)
             and writes a one-line brief per block;
  2. FILL  — writes the field values for the chosen blocks, against each
             block's fields_schema (validated by pages/fields.py);
  3. the page is materialised with variant_to_section(), i.e. rendered
             through the blocks' own templates.

Provider order (Nate, 2026-09-07): Sonnet plans and fills; Haiku is the
cheap fill fallback; Gemini is the last AI fallback; a static plan built
from the first active block per category guarantees a result.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.pages.fields import ai_schema_summary, validate_fields
from app.pages.models import SectionVariant

logger = logging.getLogger(__name__)

PLAN_MODEL = "claude-sonnet-4-5-20250929"
FILL_MODEL = "claude-sonnet-4-5-20250929"
FILL_FALLBACK_MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL = "gemini-2.5-flash"
PLAN_MAX_TOKENS = 2500
FILL_MAX_TOKENS = 6000
PLAN_TIMEOUT = 25.0
FILL_TIMEOUT = 40.0
MAX_SECTIONS = 12

CATEGORY_ORDER = [
    "nav", "hero", "features", "stats", "pricing", "gallery", "testimonials",
    "team", "faq", "booking", "location", "contact", "cta", "logos", "footer",
]

MAX_PAGES = 6
_SITE_ROLES = ("home", "about", "services", "pricing", "contact", "faq", "gallery", "blog")

# Sensible default section categories per page role — used when the AI
# names a nav destination but doesn't spell out its sections, or when the
# static fallback assembles a site.
_ROLE_COMPOSITIONS: dict[str, list[str]] = {
    "home":     ["nav", "hero", "features", "testimonials", "cta", "contact", "footer"],
    "about":    ["nav", "hero", "features", "team", "cta", "footer"],
    "services": ["nav", "hero", "services", "pricing", "faq", "cta", "footer"],
    "pricing":  ["nav", "hero", "pricing", "faq", "cta", "footer"],
    "contact":  ["nav", "hero", "contact", "footer"],
    "faq":      ["nav", "hero", "faq", "contact", "footer"],
    "gallery":  ["nav", "hero", "gallery", "cta", "footer"],
    "blog":     ["nav", "hero", "features", "cta", "footer"],
}

# Anchor / mailto / tel / external links stay as they are; only bare
# path-style hrefs ("/about", "about", "/services") become sibling pages.
_PATH_HREF = re.compile(r"^/?([a-z][a-z0-9-]{0,60})$", re.IGNORECASE)
_EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|sms:|#)", re.IGNORECASE)


def _slug_from_href(href: str) -> str | None:
    """Return the sibling-page slug an href points at, or None for
    anchors / external links / mailto / tel / already-absolute paths.
    "/" (site root) resolves to "home"."""
    if not isinstance(href, str):
        return None
    s = href.strip()
    if not s or _EXTERNAL.match(s):
        return None
    if s in ("/", ""):
        return "home"
    m = _PATH_HREF.match(s)
    if not m:
        return None
    return re.sub(r"[^a-z0-9]+", "-", m.group(1).lower()).strip("-") or None


def _slug_from_label(label: str) -> str | None:
    if not isinstance(label, str):
        return None
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s or None


def _default_role_for(slug: str) -> str:
    return slug if slug in _SITE_ROLES else "home"

PLAN_SYSTEM_PROMPT = """You plan a small-business website by choosing blocks from a fixed
library. You never write HTML, CSS or JSX and you never invent blocks: every section
MUST use a "variant_id" that appears in the catalogue.

Return STRICT JSON only:
{
  "site_title": "the business's site title",
  "audience": "one sentence: who the site is for",
  "goals": ["3-5 outcomes the site should drive"],
  "pages": [
    {
      "path": "home",                     // URL slug: home | about | services | pricing | contact | faq | gallery | blog | <your own>
      "role": "home",                     // same list of slugs, best-fit
      "title": "Page title (browser tab + h1 context)",
      "nav_label": "Word shown in the nav (short)",
      "sections": [
        {"variant_id": "<id from the catalogue>", "brief": "1-2 sentences on what this block should say for THIS business"}
      ]
    }
  ]
}

Rules:
- Return between 1 and 6 pages. Always include a "home" page first; add other pages ONLY
  when the site really needs them (a services page for a business with many services, an
  about page for a team story, a contact page with a longer form, etc.).
- The HOME page's nav block will link to every OTHER page you return. Do NOT list a page
  the visitor doesn't need — every page adds work for the owner. 1 page is a valid answer.
- Every page: 4 to 9 sections, start with a nav block if the catalogue has one, end with a
  footer block. The nav and footer should be the SAME variant_id on every page.
- Include at least one conversion block on the home page (lead form, quote calculator,
  booking picker, CTA) and at least one social-proof block (testimonials, reviews,
  stats, logos) somewhere.
- Only choose a booking block when "has_calendar" is true. Only choose "bound_data" team
  blocks when "has_team" is true.
- Prefer dynamic blocks (capabilities other than "static") when they fit.
- A variant_id can repeat across pages (nav, footer) but avoid repeating the same content
  block within one page.
- Match the requested locale in the briefs (en or fr-CA).

Legacy single-page shape (accepted for back-compat): a top-level "sections" array with no
"pages" — treated as the sole "home" page. Prefer "pages"."""

FILL_SYSTEM_PROMPT = """You are a conversion copywriter for small Canadian businesses.
For each block below, write the values of its fields. You never write HTML, CSS, JSX,
markdown or emojis (unless a field already contains them). Plain text only.

Return STRICT JSON only:
{ "sections": { "<index>": { "<FIELD_KEY>": value, ... }, ... } }

Rules:
- Respect every field's type, max_len, options (select) and list shape (item_fields,
  min_items/max_items). Numbers are numbers, booleans are booleans.
- Only write text-like fields (text, textarea, select, number, boolean, list contents).
  Never change image, url or color fields — leave them out.
- Use the business profile for names, phone, email, city and services. Never invent
  legal claims, certifications, prices or statistics the profile doesn't give; use
  round, plausible placeholder numbers where a stat is required and keep them modest.
- Write in the requested locale (en = Canadian English, fr-CA = Québec French).
- Keep headlines under 10 words, subheadlines under 25 words, buttons under 4 words."""


# ------------------------------------------------------------ catalogue ---

def _compact_desc(text: str | None, limit: int = 140) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


async def build_catalogue(db: AsyncSession) -> list[dict[str, Any]]:
    """Compact, planner-facing view of every active block."""
    rows = await db.execute(
        select(SectionVariant).where(SectionVariant.is_active.is_(True))
        .order_by(SectionVariant.category, SectionVariant.sort_order, SectionVariant.display_name)
    )
    out = []
    for v in rows.scalars().all():
        out.append({
            "variant_id": v.variant_id,
            "category": v.category,
            "name": v.display_name,
            "desc": _compact_desc(v.description),
            "caps": getattr(v, "capabilities", None) or ["static"],
            "locales": sorted((getattr(v, "locale_props", None) or {}).keys()),
        })
    return out


async def business_profile(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """What the copywriter may use as facts. Missing values stay absent so
    the model doesn't invent them."""
    profile: dict[str, Any] = {}
    try:
        from app.settings.service import get_company_settings
        c = await get_company_settings(db)
        if c is not None:
            for key, attr in (
                ("company_name", "company_name"), ("phone", "company_phone"), ("email", "company_email"),
                ("website", "company_website"), ("city", "city"), ("province", "province"),
            ):
                val = getattr(c, attr, None)
                if val:
                    profile[key] = val
    except Exception:  # noqa: BLE001
        logger.info("planner.profile_unavailable")
    try:
        from app.scheduling.models import SchedulingCalendar
        cal = (await db.execute(
            select(SchedulingCalendar).where(SchedulingCalendar.created_by == user_id, SchedulingCalendar.is_active.is_(True))
            .order_by(SchedulingCalendar.created_at).limit(1)
        )).scalars().first()
        if cal is not None:
            profile["calendar_slug"] = cal.slug
            profile["calendar_name"] = cal.name
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.auth.models import User
        owner = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if owner is not None:
            q = select(User.id).where(User.is_active.is_(True))
            q = q.where(User.org_id == owner.org_id) if owner.org_id else q.where(User.id == owner.id)
            profile["team_size"] = len((await db.execute(q)).scalars().all())
    except Exception:  # noqa: BLE001
        pass
    return profile


# ------------------------------------------------------------------ plan ---

def _sections_for_role(role: str, catalogue: list[dict], profile: dict) -> list[dict]:
    """Build a section list from a role's default composition, picking the
    first active block of each category. Skips categories with no block."""
    by_cat: dict[str, dict] = {}
    for b in catalogue:
        by_cat.setdefault(b["category"], b)
    wanted = list(_ROLE_COMPOSITIONS.get(role, _ROLE_COMPOSITIONS["home"]))
    if "booking" in wanted and not profile.get("calendar_slug"):
        wanted = [c for c in wanted if c != "booking"]
    return [
        {"variant_id": by_cat[c]["variant_id"], "brief": f"{by_cat[c]['name']} for this business."}
        for c in wanted if c in by_cat
    ]


def static_plan(prompt: str, catalogue: list[dict], profile: dict) -> dict:
    """Deterministic plan when no AI provider answers. One home page from
    the first active block per category — always renderable."""
    title = (prompt or "New site").strip().splitlines()[0][:80] or "New site"
    return {
        "site_title": title,
        "audience": "Customers looking for this business's services",
        "goals": ["Explain the offer clearly", "Build trust", "Get the visitor to reach out"],
        "pages": [{
            "path": "home", "role": "home", "title": title, "nav_label": "Home",
            "sections": _sections_for_role("home", catalogue, profile),
        }],
    }


def _normalize_sections(
    raw_sections: list, catalogue: list[dict], by_id: dict[str, dict], profile: dict,
    *, allow_repeats: set[str] | None = None,
) -> list[dict]:
    """Filter one page's sections to real library blocks. `allow_repeats`
    are variant_ids that may appear once per page (nav / footer)."""
    allow_repeats = allow_repeats or set()
    seen: set[str] = set()
    out: list[dict] = []
    for s in raw_sections or []:
        if not isinstance(s, dict):
            continue
        vid = str(s.get("variant_id") or "").strip()
        block = by_id.get(vid)
        if block is None:
            cat = str(s.get("category") or s.get("type") or "").strip()
            block = next((b for b in catalogue if b["category"] == cat), None)
            if block is None:
                logger.info("planner.unknown_variant dropped=%s", vid)
                continue
            vid = block["variant_id"]
        if vid in seen and vid not in allow_repeats:
            continue
        if "needs_calendar" in block["caps"] and not profile.get("calendar_slug"):
            continue
        seen.add(vid)
        out.append({
            "id": f"{vid}-{uuid.uuid4().hex[:6]}",
            "variant_id": vid,
            "category": block["category"],
            "type": block["category"],
            "title": block["name"],
            "summary": _compact_desc(str(s.get("brief") or s.get("summary") or ""), 240),
            "brief": str(s.get("brief") or "")[:500],
        })
    return out[:MAX_SECTIONS]


def _order_sections(sections: list[dict]) -> list[dict]:
    """Nav first, footer last, everything else in the middle preserved."""
    nav = [s for s in sections if s["category"] == "nav"][:1]
    footer = [s for s in sections if s["category"] == "footer"][-1:]
    middle = [s for s in sections if s not in nav and s not in footer]
    return nav + middle + footer


def _extract_nav_link_slugs(sections: list[dict]) -> list[tuple[str, str]]:
    """Read the nav block's NAV_LINK_n_HREF / NAV_LINK_n_TEXT pairs and
    return [(slug, label)] for the entries that look like sibling pages."""
    nav = next((s for s in sections if s["category"] == "nav"), None)
    if nav is None:
        return []
    fields = nav.get("fields") or {}
    # nav templates use NAV_LINK_{N}_TEXT / NAV_LINK_{N}_HREF (up to 6-ish)
    out: list[tuple[str, str]] = []
    for i in range(1, 10):
        href = fields.get(f"NAV_LINK_{i}_HREF")
        label = fields.get(f"NAV_LINK_{i}_TEXT") or ""
        slug = _slug_from_href(href) if href else None
        if slug and slug != "home":
            out.append((slug, label if isinstance(label, str) else ""))
    return out


def _stub_page(slug: str, label: str, catalogue: list[dict], profile: dict) -> dict:
    role = _default_role_for(slug)
    return {
        "path": slug,
        "role": role,
        "title": (label or slug.replace("-", " ").title())[:120],
        "nav_label": (label or slug.replace("-", " ").title())[:24],
        "sections": _sections_for_role(role, catalogue, profile),
    }


def normalize_plan(plan: dict | None, catalogue: list[dict], profile: dict) -> dict | None:
    """Full-site normalise. Accepts either the multi-page shape (plan.pages)
    or the legacy single-page shape (plan.sections). Returns:

        {
          "site_title": str, "audience": str, "goals": [str],
          "pages": [
             {"path", "role", "title", "nav_label", "is_home",
              "sections": [<normalized section dicts>]}
          ],
        }

    Enforces:
      - unique paths, first page becomes home ("home" path, is_home=True)
      - nav-first / footer-last per page
      - any non-anchor href in the home nav auto-adds a stub sibling page
        (with a default section composition for that role)
      - never returns booking blocks when the workspace has no calendar
      - caps at MAX_PAGES pages
    """
    if not isinstance(plan, dict):
        return None
    by_id = {b["variant_id"]: b for b in catalogue}
    # Nav + footer variant ids the site should share across pages; any
    # variant with category nav/footer is allowed to repeat once per page.
    repeat_vids = {b["variant_id"] for b in catalogue if b["category"] in ("nav", "footer")}

    raw_pages: list[dict] = []
    if isinstance(plan.get("pages"), list) and plan["pages"]:
        raw_pages = [p for p in plan["pages"] if isinstance(p, dict)]
    elif isinstance(plan.get("sections"), list):
        # Legacy single-page shape — wrap.
        raw_pages = [{
            "path": "home", "role": "home", "title": plan.get("title") or "Home",
            "nav_label": "Home", "sections": plan["sections"],
        }]

    pages: list[dict] = []
    seen_paths: set[str] = set()
    for p in raw_pages[:MAX_PAGES]:
        path = _slug_from_label(str(p.get("path") or p.get("role") or "home"))
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        role = str(p.get("role") or _default_role_for(path))[:32]
        sections = _order_sections(_normalize_sections(
            p.get("sections") or [], catalogue, by_id, profile, allow_repeats=repeat_vids,
        ))
        if not sections:
            continue
        pages.append({
            "path": path,
            "role": role,
            "title": str(p.get("title") or path.replace("-", " ").title())[:120],
            "nav_label": str(p.get("nav_label") or p.get("title") or path.replace("-", " ").title())[:24],
            "sections": sections,
        })
    if not pages:
        return None

    # First page is home, whatever it was called.
    pages[0]["path"] = "home"
    pages[0]["role"] = "home"
    for p in pages:
        p["is_home"] = (p is pages[0])

    return {
        "site_title": str(plan.get("site_title") or plan.get("title") or pages[0]["title"])[:120],
        "audience": str(plan.get("audience") or "")[:300],
        "goals": [str(g)[:160] for g in (plan.get("goals") or []) if isinstance(g, str)][:5],
        "pages": pages,
    }


def apply_nav_from_pages(plan: dict) -> dict:
    """Populate every page's nav block from `plan.pages` so the menu
    always matches the site structure. Sets NAV_LINK_n_TEXT/NAV_LINK_n_HREF
    for each OTHER page (home never appears in its own nav) and
    BRAND_NAME to the site title when not already set. Runs BEFORE
    fill_fields so the AI knows the menu is decided and only writes copy.
    """
    pages = plan.get("pages") or []
    if not pages:
        return plan
    site_title = plan.get("site_title") or plan.get("title") or ""
    for page in pages:
        for sec in page.get("sections") or []:
            if sec.get("category") != "nav":
                continue
            fields = sec.setdefault("fields", {})
            if site_title and not fields.get("BRAND_NAME"):
                fields["BRAND_NAME"] = site_title[:80]
            # Links to every OTHER page — home first if this isn't the home page.
            other = [p for p in pages if p is not page]
            slot = 1
            for other_page in other:
                if slot > 6:  # nav variants top out around 4-6 slots
                    break
                fields[f"NAV_LINK_{slot}_TEXT"] = (other_page.get("nav_label") or other_page.get("title") or other_page.get("path") or "").strip()[:24] or "Link"
                fields[f"NAV_LINK_{slot}_HREF"] = other_page.get("path") or "/"
                slot += 1
    return plan


def expand_nav_stubs(plan: dict, catalogue: list[dict], profile: dict) -> dict:
    """After fields are filled, look at the home page's nav for links that
    point to slugs the plan doesn't yet include, and add stub pages for
    each one (up to MAX_PAGES). Called after fill_fields so the nav's
    NAV_LINK_n_HREF values are populated."""
    pages = plan.get("pages") or []
    if not pages:
        return plan
    have = {p["path"] for p in pages}
    home_sections = pages[0].get("sections") or []
    added = 0
    for slug, label in _extract_nav_link_slugs(home_sections):
        if slug in have:
            continue
        if len(pages) + added >= MAX_PAGES:
            break
        stub = _stub_page(slug, label, catalogue, profile)
        by_id = {b["variant_id"]: b for b in catalogue}
        repeat_vids = {b["variant_id"] for b in catalogue if b["category"] in ("nav", "footer")}
        stub_sections = _order_sections(_normalize_sections(
            stub["sections"], catalogue, by_id, profile, allow_repeats=repeat_vids,
        ))
        if not stub_sections:
            continue
        pages.append({
            **stub, "sections": stub_sections, "is_home": False,
            "auto_added_from_nav": True,
        })
        have.add(slug)
        added += 1
    if added:
        logger.info("planner.expand_nav_stubs added=%d total_pages=%d", added, len(pages))
    return plan


def rewrite_nav_hrefs(plan: dict, website_slug: str) -> dict:
    """After all pages exist, rewrite the nav's path-style hrefs to full
    site URLs so navigation between pages works. Home stays as the
    site root; every other page becomes `/api/pages/public/site/{slug}/{path}`.
    Applied to EVERY page's nav (nav is shared)."""
    pages = plan.get("pages") or []
    if not pages:
        return plan
    slug_paths = {p["path"] for p in pages}
    root = f"/api/pages/public/site/{website_slug}"
    for p in pages:
        for sec in p.get("sections") or []:
            if sec.get("category") != "nav":
                continue
            fields = sec.setdefault("fields", {}) if isinstance(sec.get("fields"), dict) else sec.setdefault("fields", {})
            for i in range(1, 10):
                href_key = f"NAV_LINK_{i}_HREF"
                href = fields.get(href_key)
                slug = _slug_from_href(href) if isinstance(href, str) else None
                if slug is None:
                    continue
                if slug == "home":
                    fields[href_key] = root
                elif slug in slug_paths:
                    fields[href_key] = f"{root}/{slug}"
                # else: leave as-is; visitor gets a 404, owner can edit
    return plan


async def plan_page(
    db: AsyncSession, prompt: str, settings: Settings, *, user_id: uuid.UUID,
    locale: str = "en", previous_plan: dict | None = None,
) -> tuple[dict, str, list[dict], dict]:
    """Returns (plan, provider, catalogue, profile). Never raises."""
    from app.pages.conversational import _claude_call_json, _gemini_call_json

    catalogue = await build_catalogue(db)
    profile = await business_profile(db, user_id)
    user_msg = (
        f"Locale: {locale}\n"
        f"has_calendar: {bool(profile.get('calendar_slug'))}\n"
        f"has_team: {int(profile.get('team_size') or 0) > 1}\n\n"
        f"Business profile (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"Block catalogue (JSON, choose by variant_id):\n"
        f"{json.dumps([{k: b[k] for k in ('variant_id', 'category', 'name', 'desc', 'caps')} for b in catalogue], ensure_ascii=False)}\n\n"
        + (f"Current plan the user wants changed (JSON):\n{json.dumps({'title': previous_plan.get('title'), 'sections': [{'variant_id': s.get('variant_id'), 'brief': s.get('brief')} for s in previous_plan.get('sections', [])]}, ensure_ascii=False)}\n\n" if previous_plan else "")
        + f"User request:\n{prompt}"
    )
    plan: dict | None = None
    provider = "static_fallback"
    if getattr(settings, "anthropic_api_key", None):
        try:
            raw = await _claude_call_json(settings=settings, model=PLAN_MODEL, system_prompt=PLAN_SYSTEM_PROMPT,
                                          user_msg=user_msg, max_tokens=PLAN_MAX_TOKENS, timeout=PLAN_TIMEOUT)
            plan = normalize_plan(raw, catalogue, profile)
            provider = "claude"
        except Exception as exc:  # noqa: BLE001
            logger.warning("planner.plan_claude_failed err=%s", str(exc)[:200])
    if plan is None and (getattr(settings, "gemini_api_key", "") or ""):
        try:
            raw = await _gemini_call_json(api_key=settings.gemini_api_key, model=GEMINI_MODEL, system_prompt=PLAN_SYSTEM_PROMPT,
                                          user_msg=user_msg, max_tokens=PLAN_MAX_TOKENS, timeout=PLAN_TIMEOUT)
            plan = normalize_plan(raw, catalogue, profile)
            provider = "gemini_fallback"
        except Exception as exc:  # noqa: BLE001
            logger.warning("planner.plan_gemini_failed err=%s", str(exc)[:200])
    if plan is None:
        plan = normalize_plan(static_plan(prompt, catalogue, profile), catalogue, profile) or static_plan(prompt, catalogue, profile)
        provider = "static_fallback"
    logger.info("planner.plan provider=%s sections=%d", provider, len(plan.get("sections", [])))
    return plan, provider, catalogue, profile


# ------------------------------------------------------------------ fill ---

_LOCKED_TYPES = ("image", "url", "color")


SITEMAP_SYSTEM_PROMPT = """You are a small-business web strategist. The user describes a
business; you propose a short list of pages the site should have (never markup, never
copy — just a plan).

Return STRICT JSON only:
{
  "site_title": "the business's site name",
  "audience": "one short sentence: who the site serves",
  "recommendation": "one or two sentences explaining why THIS page count fits",
  "pages": [
    {"path": "home",    "role": "home",     "title": "Home",     "nav_label": "Home",     "purpose": "1 sentence"},
    {"path": "about",   "role": "about",    "title": "About",    "nav_label": "About",    "purpose": "1 sentence"}
  ]
}

Rules:
- 1 to 5 pages. Recommend the smallest set that fits the business — every page adds work
  for the owner. A solo consultant may need only home. A restaurant may need home + menu
  + contact. A dental clinic may need home + services + team + contact.
- Always include a "home" page first. Common roles: home, about, services, pricing,
  contact, faq, gallery, blog. Pick fresh `path` slugs if the business needs pages that
  aren't in that list (e.g. "menu" for a restaurant).
- `purpose` is one line the user will read to decide whether to keep the page.
- Match the requested locale in titles/nav labels/purposes (en or fr-CA)."""


async def plan_from_sitemap(
    db: AsyncSession, prompt: str, settings: Settings, *,
    user_id: uuid.UUID, locale: str, pages: list[dict],
) -> tuple[dict, str, list[dict], dict]:
    """Skip the plan call entirely when the user already confirmed a
    sitemap: build each page's sections from its role's default
    composition (still using real library variants). Returns the same
    tuple shape as `plan_page`."""
    catalogue = await build_catalogue(db)
    profile = await business_profile(db, user_id)
    raw = {
        "site_title": pages and pages[0].get("site_title") or "",
        "audience": "",
        "goals": [],
        "pages": [
            {
                "path": p.get("path") or _slug_from_label(str(p.get("title") or "")) or f"page-{i}",
                "role": p.get("role") or _default_role_for(str(p.get("path") or "home")),
                "title": p.get("title") or (p.get("path") or "").replace("-", " ").title(),
                "nav_label": p.get("nav_label") or p.get("title") or "",
                # Use the default composition for the role — the fill
                # step then writes copy through each block's fields.
                "sections": _sections_for_role(
                    p.get("role") or _default_role_for(str(p.get("path") or "home")),
                    catalogue, profile,
                ),
            }
            for i, p in enumerate(pages[:MAX_PAGES]) if isinstance(p, dict)
        ],
    }
    plan = normalize_plan(raw, catalogue, profile) or static_plan(prompt, catalogue, profile)
    logger.info("planner.plan_from_sitemap pages=%d", len(plan.get("pages", [])))
    return plan, "sitemap_confirmed", catalogue, profile


async def suggest_sitemap(
    db: AsyncSession, prompt: str, settings: Settings, *, user_id: uuid.UUID, locale: str = "en",
) -> tuple[dict, str, dict]:
    """Cheap first step: ask Sonnet to propose a page list ONLY. No blocks,
    no copy. The user confirms / edits before we spend fill tokens.
    Returns (sitemap, provider, profile). Sitemap shape:
      {site_title, audience, recommendation, pages: [{path, role, title, nav_label, purpose}]}
    Never raises — a hand-built default (home only) is the last resort.
    """
    from app.pages.conversational import _claude_call_json, _gemini_call_json

    profile = await business_profile(db, user_id)
    user_msg = (
        f"Locale: {locale}\n"
        f"Business profile (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"User request:\n{prompt}"
    )
    result: dict | None = None
    provider = "static_fallback"
    if getattr(settings, "anthropic_api_key", None):
        try:
            result = await _claude_call_json(
                settings=settings, model=PLAN_MODEL, system_prompt=SITEMAP_SYSTEM_PROMPT,
                user_msg=user_msg, max_tokens=1200, timeout=PLAN_TIMEOUT,
            )
            provider = "claude"
        except Exception as exc:  # noqa: BLE001
            logger.warning("planner.sitemap_claude_failed err=%s", str(exc)[:200])
    if result is None and (getattr(settings, "gemini_api_key", "") or ""):
        try:
            result = await _gemini_call_json(
                api_key=settings.gemini_api_key, model=GEMINI_MODEL, system_prompt=SITEMAP_SYSTEM_PROMPT,
                user_msg=user_msg, max_tokens=1200, timeout=PLAN_TIMEOUT,
            )
            provider = "gemini_fallback"
        except Exception as exc:  # noqa: BLE001
            logger.warning("planner.sitemap_gemini_failed err=%s", str(exc)[:200])

    sitemap = _normalize_sitemap(result, prompt)
    logger.info("planner.sitemap provider=%s pages=%d", provider, len(sitemap["pages"]))
    return sitemap, provider, profile


def _normalize_sitemap(raw: Any, prompt: str) -> dict:
    """Coerce whatever the AI returned into a small, sane sitemap. Always
    returns at least one home page."""
    pages: list[dict] = []
    if isinstance(raw, dict) and isinstance(raw.get("pages"), list):
        seen: set[str] = set()
        for p in raw["pages"][:MAX_PAGES]:
            if not isinstance(p, dict):
                continue
            path = _slug_from_label(str(p.get("path") or p.get("role") or p.get("title") or ""))
            if not path or path in seen:
                continue
            seen.add(path)
            pages.append({
                "path": path,
                "role": str(p.get("role") or _default_role_for(path))[:32],
                "title": str(p.get("title") or path.replace("-", " ").title())[:120],
                "nav_label": str(p.get("nav_label") or p.get("title") or path.replace("-", " ").title())[:24],
                "purpose": str(p.get("purpose") or "")[:200],
            })
    if not pages:
        pages = [{"path": "home", "role": "home", "title": "Home", "nav_label": "Home",
                  "purpose": "A single landing page — you can add more later."}]
    else:
        pages[0] = {**pages[0], "path": "home", "role": "home"}
    site_title = str((raw or {}).get("site_title") or (prompt or "New site").splitlines()[0][:80] or "New site")[:120]
    return {
        "site_title": site_title,
        "audience": str((raw or {}).get("audience") or "")[:300],
        "recommendation": str((raw or {}).get("recommendation") or "")[:400],
        "pages": pages,
    }


async def fill_fields(
    db: AsyncSession, plan: dict, settings: Settings, *, profile: dict, locale: str = "en", prompt: str = "",
) -> tuple[dict, str]:
    """Write field values for every planned section across every page.
    Mutates plan sections in place (adds `fields`, `thumbnail_url`) and
    returns (plan, provider). Validation drops anything off-schema;
    locked field types are never overwritten."""
    from app.pages.conversational import _claude_call_json, _gemini_call_json
    from app.pages.variants import effective_props

    pages = plan.get("pages") or []
    # Collect every section from every page, along with page + section
    # coordinates so we can write back the AI's reply.
    coords: list[tuple[int, int, dict]] = []
    for pi, p in enumerate(pages):
        for si, s in enumerate(p.get("sections") or []):
            coords.append((pi, si, s))

    ids = [s["variant_id"] for _, _, s in coords]
    rows = await db.execute(select(SectionVariant).where(SectionVariant.variant_id.in_(ids), SectionVariant.is_active.is_(True)))
    variants = {v.variant_id: v for v in rows.scalars().all()}

    jobs = []
    for job_index, (pi, si, s) in enumerate(coords):
        v = variants.get(s["variant_id"])
        if v is None:
            continue
        s["thumbnail_url"] = v.preview_thumbnail_url
        defaults, _ = effective_props(v, locale=locale)
        # apply_nav_from_pages may have pre-set NAV_LINK_* fields on nav
        # blocks; keep them as the AI's "current" values so the model
        # sees the correct site structure but knows not to invent links.
        preset = s.get("fields") or {}
        defaults = {**defaults, **preset}
        schema = getattr(v, "fields_schema", None) or []
        editable = [f for f in ai_schema_summary(schema) if f["type"] not in _LOCKED_TYPES]
        keys = {f["key"] for f in editable}
        page = pages[pi]
        jobs.append({
            "index": job_index, "page": page.get("path"), "page_role": page.get("role"),
            "variant_id": v.variant_id, "block": f"{v.display_name} ({v.category})",
            "brief": s.get("brief") or s.get("summary") or "",
            "schema": editable,
            "current": {k: val for k, val in defaults.items() if k in keys},
        })
    if not jobs:
        return plan, "none"

    user_msg = (
        f"Locale: {locale}\nSite title: {plan.get('site_title') or plan.get('title')}\n"
        f"Audience: {plan.get('audience')}\n"
        f"Goals: {json.dumps(plan.get('goals') or [], ensure_ascii=False)}\n"
        f"Pages in this site: {json.dumps([p.get('path') for p in pages], ensure_ascii=False)}\n"
        f"Original request: {prompt[:1500]}\n\n"
        f"Business profile (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"Blocks to write (JSON):\n{json.dumps(jobs, ensure_ascii=False)}\n\n"
        f"Nav block guidance: NAV_LINK_n_TEXT should match a page in the list above; "
        f"NAV_LINK_n_HREF should be that page's path (e.g. \"about\", \"services\"). "
        f"Home is \"/\". Do NOT put anchors like \"#pricing\" for links that should go "
        f"to their own page."
    )
    result: dict | None = None
    provider = "defaults"
    if getattr(settings, "anthropic_api_key", None):
        for model, label in ((FILL_MODEL, "claude"), (FILL_FALLBACK_MODEL, "claude_haiku")):
            try:
                result = await _claude_call_json(settings=settings, model=model, system_prompt=FILL_SYSTEM_PROMPT,
                                                 user_msg=user_msg, max_tokens=FILL_MAX_TOKENS, timeout=FILL_TIMEOUT)
                provider = label
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("planner.fill_failed model=%s err=%s", model, str(exc)[:200])
    if result is None and (getattr(settings, "gemini_api_key", "") or ""):
        try:
            result = await _gemini_call_json(api_key=settings.gemini_api_key, model=GEMINI_MODEL, system_prompt=FILL_SYSTEM_PROMPT,
                                             user_msg=user_msg, max_tokens=FILL_MAX_TOKENS, timeout=FILL_TIMEOUT)
            provider = "gemini_fallback"
        except Exception as exc:  # noqa: BLE001
            logger.warning("planner.fill_gemini_failed err=%s", str(exc)[:200])

    written = (result or {}).get("sections") if isinstance(result, dict) else None
    if not isinstance(written, dict):
        written = {}
    for job in jobs:
        pi, si, s = coords[job["index"]]
        v = variants[job["variant_id"]]
        # Preserve pre-set fields (nav links, brand name) written by
        # apply_nav_from_pages so the AI's fill can't overwrite the
        # site structure.
        preset = s.get("fields") or {}
        schema = getattr(v, "fields_schema", None) or []
        locked = {f["key"] for f in schema if f.get("type") in _LOCKED_TYPES}
        proposed = written.get(str(job["index"])) or written.get(job["index"]) or {}
        if not isinstance(proposed, dict):
            proposed = {}
        proposed = {k: val for k, val in proposed.items() if k not in locked}
        merged = {**job["current"], **proposed}
        clean, errors = validate_fields(schema, merged, locale=locale)
        if errors:
            logger.info("planner.fill_field_errors variant=%s errors=%s", v.variant_id, errors[:4])
        # Only keep keys the AI (or defaults) actually provided; media
        # stays with the block. Nav's pre-set NAV_LINK_*/BRAND_NAME
        # values (from apply_nav_from_pages) win over AI overwrites.
        s["fields"] = {**{k: val for k, val in clean.items() if k not in locked}, **preset}
    return plan, provider
