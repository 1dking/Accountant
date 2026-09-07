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


async def resolve_company(db: AsyncSession, page: Page) -> dict[str, Any]:
    from app.settings.service import get_company_settings

    company = await get_company_settings(db)
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
    }
    return {k: v for k, v in out.items() if v}


async def resolve_users(db: AsyncSession, page: Page) -> dict[str, Any]:
    """Team grid: active users in the page owner's workspace (same org, or
    the owner alone when there is no org)."""
    from app.auth.models import User

    owner = (await db.execute(select(User).where(User.id == page.created_by))).scalar_one_or_none()
    if owner is None:
        return {}
    q = select(User).where(User.is_active.is_(True))
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
            "BOOKING_HREF": u.booking_link or "",
            "INITIALS": "".join(p[0] for p in u.full_name.split()[:2]).upper(),
        }
        for u in users
    ]
    return {"TEAM": team} if team else {}


RESOLVERS: dict[str, Resolver] = {
    "company": resolve_company,
    "users": resolve_users,
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
