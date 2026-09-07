"""Data binding for block model v2.

A block declares `data_source` (company | users | …) and `data_mode`:

- compile → `resolve_page_bindings()` runs at publish time, merges the
  workspace data into the section's props and re-renders the template.
  The stored `sections_json` is NOT modified (the resolved copy is what
  gets compiled), so the editor keeps showing the block's own defaults
  and an edit to the source data only needs a republish.
- live → nothing happens here; the runtime fetches
  `/api/pages/public/{slug}/data/...` in the browser.

Resolvers return a props dict whose keys are the block's tokens. Sources
that need the S5 tables (products, reviews, faqs, pricing) are wired
there; this module ships company + users so the contract is exercised.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pages.models import Page

logger = logging.getLogger(__name__)

Resolver = Callable[[AsyncSession, Page], Awaitable[dict[str, Any]]]


async def _page_owner(db: AsyncSession, page: Page):
    from app.auth.models import User
    return (await db.execute(select(User).where(User.id == page.created_by))).scalar_one_or_none()


async def resolve_company(db: AsyncSession, page: Page) -> dict[str, Any]:
    """Company profile scoped to the page's owner (or their org).

    Falls back to the singleton row when no per-owner row exists so a
    freshly-installed workspace still fills COMPANY_* tokens."""
    from app.settings.models import CompanySettings

    owner = await _page_owner(db, page)
    company = None
    if owner is not None:
        q = select(CompanySettings)
        q = q.where(CompanySettings.org_id == owner.org_id) if owner.org_id else q.where(CompanySettings.created_by == owner.id)
        company = (await db.execute(q.limit(1))).scalars().first()
    if company is None:
        company = (await db.execute(select(CompanySettings).limit(1))).scalars().first()
    if company is None:
        return {}
    address = ", ".join(
        p for p in (
            getattr(company, "address_line1", None) or getattr(company, "address", None),
            company.city, company.state or company.province, company.zip_code,
        ) if p
    )
    out = {
        "COMPANY_NAME": company.company_name,
        "COMPANY_PHONE": company.company_phone,
        "COMPANY_EMAIL": company.company_email,
        "COMPANY_WEBSITE": company.company_website,
        "COMPANY_ADDRESS": address or None,
        "COMPANY_LOGO_URL": "/api/settings/company/logo" if company.logo_storage_path else None,
        "COMPANY_TAGLINE": getattr(company, "tagline", None),
        "SERVICE_AREA": getattr(company, "service_area_text", None),
        "MAP_EMBED_URL": getattr(company, "map_embed_url", None),
        "BRAND_PRIMARY_COLOR": getattr(company, "brand_primary_color", None),
    }
    return {k: v for k, v in out.items() if v}


async def resolve_users(db: AsyncSession, page: Page) -> dict[str, Any]:
    """Team grid: active users in the page owner's workspace who opted
    into the public site (User.show_on_site)."""
    from app.auth.models import User

    owner = await _page_owner(db, page)
    if owner is None:
        return {}
    q = select(User).where(User.is_active.is_(True), User.show_on_site.is_(True))
    if owner.org_id:
        q = q.where(User.org_id == owner.org_id)
    else:
        q = q.where(User.id == owner.id)
    users = (await db.execute(q.order_by(User.full_name))).scalars().all()
    team = [
        {
            "NAME": u.full_name,
            "TITLE": getattr(u, "public_title", None) or u.role.value.replace("_", " ").title(),
            "AVATAR_URL": getattr(u, "avatar_url", None) or "",
            "BIO": (getattr(u, "public_bio", None) or "")[:400],
            "BOOKING_HREF": u.booking_link or "",
            "INITIALS": "".join(p[0] for p in u.full_name.split()[:2]).upper(),
        }
        for u in users
    ]
    return {"TEAM": team} if team else {}


async def resolve_catalog(db: AsyncSession, page: Page) -> dict[str, Any]:
    """Services / products / plans owned by the page's workspace."""
    from app.pages import catalog_service

    owner = await _page_owner(db, page)
    if owner is None:
        return {}
    items = await catalog_service.list_catalog(db, owner)
    if not items:
        return {}                       # nothing to bind — keep the sample copy
    services = [_service_row(catalog_service.catalog_out(i)) for i in items if i.kind == "service"]
    products = [_product_row(catalog_service.catalog_out(i)) for i in items if i.kind == "product"]
    plans = [_plan_row(catalog_service.catalog_out(i)) for i in items if i.kind == "plan"]
    out: dict[str, Any] = {}
    if services: out["SERVICES"] = services
    if products: out["PRODUCTS"] = products
    if plans:    out["PLANS"] = plans
    return out


async def resolve_reviews(db: AsyncSession, page: Page) -> dict[str, Any]:
    from app.pages import catalog_service

    owner = await _page_owner(db, page)
    if owner is None:
        return {}
    rows = await catalog_service.list_reviews(db, owner, limit=12)
    out = [
        {
            "QUOTE": r.quote,
            "AUTHOR_NAME": r.author_name,
            "AUTHOR_TITLE": r.author_title or "",
            "AUTHOR_AVATAR_URL": r.author_avatar_url or "",
            "RATING": r.rating or 0,
            "STARS": "★" * (r.rating or 0),
            "SOURCE": r.source,
            "INITIALS": "".join(p[0] for p in r.author_name.split()[:2]).upper(),
        }
        for r in rows
    ]
    return {"REVIEWS": out} if out else {}


async def resolve_faqs(db: AsyncSession, page: Page) -> dict[str, Any]:
    from app.pages import catalog_service

    owner = await _page_owner(db, page)
    if owner is None:
        return {}
    rows = await catalog_service.list_faqs(db, owner, limit=40)
    out = [{"QUESTION": f.question, "ANSWER": f.answer, "CATEGORY": f.category or ""} for f in rows]
    return {"FAQS": out} if out else {}


def _service_row(s: dict) -> dict:
    return {
        "NAME": s["name"], "SLUG": s["slug"], "SUMMARY": s.get("summary") or "",
        "DESCRIPTION": s.get("description") or "", "PRICE_DISPLAY": s.get("price_display") or "",
        "PRICE_PERIOD": s.get("price_period") or "", "IMAGE_URL": s.get("image_url") or "",
        "CTA_TEXT": s.get("cta_text") or "", "CTA_HREF": s.get("cta_href") or "",
        "FEATURES": s.get("features") or [],
    }


def _product_row(s: dict) -> dict:
    return {**_service_row(s), "STRIPE_PRICE_ID": s.get("stripe_price_id") or ""}


def _plan_row(s: dict) -> dict:
    return {
        **_service_row(s),
        "FEATURED": bool(s.get("is_featured")),
    }


RESOLVERS: dict[str, Resolver] = {
    "company": resolve_company,
    "users": resolve_users,
    "catalog": resolve_catalog,
    "reviews": resolve_reviews,
    "faqs": resolve_faqs,
}


async def resolve_page_bindings(db: AsyncSession, page: Page) -> str | None:
    """Return a resolved copy of `page.sections_json` (or None when no
    section needs compile-time data). Each bound section's props are
    merged with the resolver output and its jsx_content re-rendered."""
    try:
        sections = json.loads(page.sections_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(sections, list):
        return None

    bound = [
        s for s in sections
        if isinstance(s, dict)
        and (s.get("metadata") or {}).get("data_source") in RESOLVERS
        and (s.get("metadata") or {}).get("data_mode", "compile") == "compile"
    ]
    if not bound:
        return None

    from app.pages.models import SectionVariant
    from app.pages.variants import EMBED_TOKENS, MEDIA_TOKENS, render_template

    cache: dict[str, dict[str, Any]] = {}
    variant_ids = {s["metadata"].get("variant_id") for s in bound if s["metadata"].get("variant_id")}
    templates: dict[str, SectionVariant] = {}
    if variant_ids:
        rows = await db.execute(select(SectionVariant).where(SectionVariant.variant_id.in_(variant_ids)))
        templates = {v.variant_id: v for v in rows.scalars().all()}

    changed = False
    for sec in bound:
        meta = sec["metadata"]
        source = meta["data_source"]
        if source not in cache:
            try:
                cache[source] = await RESOLVERS[source](db, page)
            except Exception:  # noqa: BLE001
                logger.exception("pages.bindings.resolver_failed source=%s page_id=%s", source, page.id)
                cache[source] = {}
        data = cache[source]
        variant = templates.get(meta.get("variant_id"))
        if not data or variant is None or sec.get("edited_html"):
            continue  # nothing to bind, or the user hand-edited this render
        props = {**(meta.get("props") or {}), **data}
        is_v2 = int(getattr(variant, "schema_version", 1) or 1) >= 2
        sec["jsx_content"] = render_template(
            variant.jsx_template, props, skip_tokens=MEDIA_TOKENS | EMBED_TOKENS, escape=is_v2,
        )
        meta["props"] = props
        meta["bound_at_publish"] = True
        changed = True
    return json.dumps(sections) if changed else None
