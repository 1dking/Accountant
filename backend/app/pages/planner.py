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

PLAN_SYSTEM_PROMPT = """You plan one web page for a small Canadian business by choosing
blocks from a fixed library. You never write HTML, CSS or JSX and you never invent
blocks: every section MUST use a "variant_id" that appears in the catalogue.

Return STRICT JSON only:
{
  "title": "page title (browser tab + h1 context)",
  "audience": "one sentence: who the page is for",
  "goals": ["3-5 outcomes the page should drive"],
  "sections": [
    {"variant_id": "<id from the catalogue>", "brief": "1-2 sentences on what this block should say for THIS business"}
  ]
}

Rules:
- 5 to 10 sections. Start with a nav block if the catalogue has one; end with a footer block.
- Include at least one conversion block (lead form, quote calculator, booking picker, CTA)
  and at least one social-proof block (testimonials, reviews, stats, logos) when available.
- Only choose a booking block when "has_calendar" is true. Only choose "bound_data" team
  blocks when "has_team" is true.
- Prefer dynamic blocks (capabilities other than "static") when they fit the business.
- Use each variant_id at most once. Do not pad with sections the business doesn't need.
- Match the requested locale in the briefs (en or fr-CA)."""

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

def static_plan(prompt: str, catalogue: list[dict], profile: dict) -> dict:
    """Deterministic plan from the first active block per category — used
    when no AI provider answers. Always renderable."""
    by_cat: dict[str, dict] = {}
    for b in catalogue:
        by_cat.setdefault(b["category"], b)
    wanted = ["nav", "hero", "features", "testimonials", "faq"]
    wanted.append("booking" if profile.get("calendar_slug") and "booking" in by_cat else "contact")
    wanted.append("footer")
    sections = [
        {"variant_id": by_cat[c]["variant_id"], "brief": f"{by_cat[c]['name']} for this business."}
        for c in wanted if c in by_cat
    ]
    title = (prompt or "New page").strip().splitlines()[0][:80] or "New page"
    return {
        "title": title,
        "audience": "Customers looking for this business's services",
        "goals": ["Explain the offer clearly", "Build trust", "Get the visitor to reach out"],
        "sections": sections,
    }


def normalize_plan(plan: dict | None, catalogue: list[dict], profile: dict) -> dict | None:
    """Keep only sections whose variant_id exists; dedupe; cap; enforce
    nav-first / footer-last ordering; drop booking blocks without a
    calendar. Returns None if nothing usable remains."""
    if not isinstance(plan, dict):
        return None
    by_id = {b["variant_id"]: b for b in catalogue}
    seen: set[str] = set()
    sections: list[dict] = []
    for s in plan.get("sections") or []:
        if not isinstance(s, dict):
            continue
        vid = str(s.get("variant_id") or "").strip()
        block = by_id.get(vid)
        if block is None:
            # unknown id — fall back to the first block of the mentioned category
            cat = str(s.get("category") or s.get("type") or "").strip()
            block = next((b for b in catalogue if b["category"] == cat), None)
            if block is None:
                logger.info("planner.unknown_variant dropped=%s", vid)
                continue
            vid = block["variant_id"]
        if vid in seen:
            continue
        if "needs_calendar" in block["caps"] and not profile.get("calendar_slug"):
            continue
        seen.add(vid)
        sections.append({
            "id": f"{vid}-{uuid.uuid4().hex[:6]}",
            "variant_id": vid,
            "category": block["category"],
            "type": block["category"],
            "title": block["name"],
            "summary": _compact_desc(str(s.get("brief") or s.get("summary") or ""), 240),
            "brief": str(s.get("brief") or "")[:500],
        })
    if not sections:
        return None
    sections = sections[:MAX_SECTIONS]
    nav = [s for s in sections if s["category"] == "nav"][:1]
    footer = [s for s in sections if s["category"] == "footer"][-1:]
    middle = [s for s in sections if s not in nav and s not in footer]
    ordered = nav + middle + footer
    return {
        "title": str(plan.get("title") or "New page")[:120],
        "audience": str(plan.get("audience") or "")[:300],
        "goals": [str(g)[:160] for g in (plan.get("goals") or []) if isinstance(g, str)][:5],
        "sections": ordered,
    }


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


async def fill_fields(
    db: AsyncSession, plan: dict, settings: Settings, *, profile: dict, locale: str = "en", prompt: str = "",
) -> tuple[dict, str]:
    """Write field values for every planned section. Mutates plan
    sections in place (adds `fields`, `thumbnail_url`) and returns
    (plan, provider). Validation drops anything off-schema; locked
    field types are never overwritten."""
    from app.pages.conversational import _claude_call_json, _gemini_call_json
    from app.pages.variants import effective_props

    sections = plan.get("sections") or []
    ids = [s["variant_id"] for s in sections]
    rows = await db.execute(select(SectionVariant).where(SectionVariant.variant_id.in_(ids), SectionVariant.is_active.is_(True)))
    variants = {v.variant_id: v for v in rows.scalars().all()}

    jobs = []
    for i, s in enumerate(sections):
        v = variants.get(s["variant_id"])
        if v is None:
            continue
        s["thumbnail_url"] = v.preview_thumbnail_url
        defaults, _ = effective_props(v, locale=locale)
        schema = getattr(v, "fields_schema", None) or []
        editable = [f for f in ai_schema_summary(schema) if f["type"] not in _LOCKED_TYPES]
        keys = {f["key"] for f in editable}
        jobs.append({
            "index": i, "variant_id": v.variant_id, "block": f"{v.display_name} ({v.category})",
            "brief": s.get("brief") or s.get("summary") or "",
            "schema": editable,
            "current": {k: val for k, val in defaults.items() if k in keys},
        })
    if not jobs:
        return plan, "none"

    user_msg = (
        f"Locale: {locale}\nPage title: {plan.get('title')}\nAudience: {plan.get('audience')}\n"
        f"Goals: {json.dumps(plan.get('goals') or [], ensure_ascii=False)}\n"
        f"Original request: {prompt[:1500]}\n\n"
        f"Business profile (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"Blocks to write (JSON):\n{json.dumps(jobs, ensure_ascii=False)}"
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
        s = sections[job["index"]]
        v = variants[job["variant_id"]]
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
        # only keep keys the AI (or defaults) actually provided; media stays with the block
        s["fields"] = {k: val for k, val in clean.items() if k not in locked}
    return plan, provider
