"""Variant library service — token substitution + content migration.

Renders a SectionVariant template by substituting {{TOKEN}} placeholders
with values from default_props (override-able). Used by:
  - POST /sections   — inserting a new section from a variant
  - POST /sections/{idx}/change-variant — swapping variant on existing
    section, preserving content where tokens match
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pages.models import SectionVariant


_TOKEN_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def render_template(template: str, props: dict[str, Any]) -> str:
    """Substitute {{TOKEN}} occurrences. Unresolved tokens are kept
    intact (user can fill them in via the inline editor)."""
    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        val = props.get(key)
        if val is None:
            return match.group(0)  # leave the placeholder visible
        return str(val)
    return _TOKEN_RE.sub(_sub, template or "")


def extract_token_values(rendered_html: str, template: str) -> dict[str, str]:
    """Best-effort: given a rendered section's HTML and the template
    it came from, infer the {{TOKEN}} -> actual-value mapping by
    diffing positions.

    Approach: split template on token boundaries → for each pair of
    adjacent literal chunks, find the corresponding text between them
    in the rendered HTML and assign that substring to the token.

    This is intentionally simple — it works for clean substitutions
    (no nested tokens, no whitespace changes between literal chunks)
    and falls back to silently dropping tokens that can't be resolved.
    """
    if not rendered_html or not template:
        return {}
    parts = _TOKEN_RE.split(template)
    # parts alternates: [literal, token, literal, token, ..., literal]
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    cursor = 0
    for i in range(1, len(parts), 2):
        token = parts[i]
        before = parts[i - 1]
        after = parts[i + 1] if i + 1 < len(parts) else ""
        # find `before` starting from cursor
        before_idx = rendered_html.find(before, cursor)
        if before_idx < 0:
            continue
        value_start = before_idx + len(before)
        # find `after` after value_start. If `after` is empty, take
        # to end of html.
        if after:
            # Take the first non-empty literal chunk from `after` to
            # avoid matching whitespace-only boundaries.
            anchor = after.lstrip()[:32]
            if not anchor:
                continue
            after_idx = rendered_html.find(anchor, value_start)
            if after_idx < 0:
                continue
            value = rendered_html[value_start:after_idx].strip()
        else:
            value = rendered_html[value_start:].strip()
        if value and len(value) < 2000:
            out[token] = value
        cursor = value_start
    return out


async def get_variant(
    db: AsyncSession, category: str, variant_id: str,
) -> SectionVariant | None:
    """Fetch one variant by category + variant_id. Returns None if
    not found or inactive."""
    rows = await db.execute(
        select(SectionVariant).where(
            SectionVariant.category == category,
            SectionVariant.variant_id == variant_id,
            SectionVariant.is_active.is_(True),
        )
    )
    return rows.scalar_one_or_none()


async def list_variants(
    db: AsyncSession, category: str | None = None,
) -> list[SectionVariant]:
    """List active variants. If category is provided, filter to that
    category. Ordered by sort_order ASC, display_name ASC."""
    stmt = select(SectionVariant).where(SectionVariant.is_active.is_(True))
    if category:
        stmt = stmt.where(SectionVariant.category == category)
    stmt = stmt.order_by(SectionVariant.sort_order, SectionVariant.display_name)
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


def variant_to_section(
    variant: SectionVariant, *, prop_overrides: dict | None = None,
) -> dict:
    """Build a section dict ready to insert into sections_json from
    a variant + optional prop overrides. The result has:
      - id: uuid-based
      - type: derived from category
      - variant_id: which variant this came from
      - jsx_content: rendered template
      - metadata: includes default_props snapshot for future migrations
    """
    props = {**(variant.default_props or {}), **(prop_overrides or {})}
    rendered = render_template(variant.jsx_template, props)
    return {
        "id": f"{variant.variant_id}-{uuid.uuid4().hex[:6]}",
        "type": variant.category,
        "title": variant.display_name,
        "summary": variant.description or "",
        "jsx_content": rendered,
        "metadata": {
            "variant_id": variant.variant_id,
            "props": props,
        },
    }


async def seed_if_empty(db: AsyncSession) -> int:
    """Insert seed variants if the table is empty. Idempotent — does
    nothing once any rows exist. Returns count inserted."""
    from app.pages.variant_seeds import all_variants

    rows = await db.execute(select(SectionVariant).limit(1))
    if rows.first():
        return 0

    inserted = 0
    for v in all_variants():
        row = SectionVariant(
            id=v["id"],
            category=v["category"],
            variant_id=v["variant_id"],
            display_name=v["display_name"],
            description=v.get("description"),
            jsx_template=v["jsx_template"],
            default_props=v.get("default_props", {}),
            sort_order=v.get("sort_order", 100),
            is_active=True,
        )
        db.add(row)
        inserted += 1
    await db.commit()
    return inserted
