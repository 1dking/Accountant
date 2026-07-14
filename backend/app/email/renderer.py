"""Override-aware email renderer.

``render_email(db, template_key, user_id, **variables)`` is the
single chokepoint that every outbound-email caller should go through.

Resolution:
  1. Look for an EmailTemplateOverride row for (user_id, template_key).
  2. If present:
       - subject = subject_override (if set) else default_subject
       - body   = body_override (if set + allows_body_override) else system Jinja2
     ``{placeholder}`` substitution applies to override strings. Values
     are HTML-escaped where they end up in HTML context, except for
     pre-rendered URL variables, which we trust the caller already
     escaped at the boundary (URL builder).
  3. If no override row: render the system Jinja2 template by name.

Substitution is intentionally NOT Jinja2:
  - admin-authored bodies can't write ``{% include %}``, ``{{ user.password_hash }}``,
    or attribute-walking expressions
  - the surface area is tiny: replace ``{key}`` with ``str(values[key])`` once
  - unknown ``{whatever}`` is left as the literal text (better than raising,
    so a stale override after a schema change still mostly works)
"""
from __future__ import annotations

import html
import logging
import re
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.email.models import EmailTemplateOverride
from app.email.template_schemas import TEMPLATES, get_schema

logger = logging.getLogger(__name__)

# Placeholders that hold pre-built URLs — we trust the caller produced
# them safely. Skipping HTML-escape on these preserves any "&amp;" the
# URL builder already encoded.
_URL_VARS = frozenset({
    "reset_url",
    "invite_link",
    "link_url",
    "view_url",
    "preferences_url",
    "action_url",
    "payment_url",
})

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _substitute(template_text: str, values: dict[str, Any]) -> str:
    """Replace ``{key}`` tokens with HTML-escaped values from ``values``.

    Unknown tokens are left in place (don't blow up if an admin's old
    override references a placeholder we no longer pass). None values
    are substituted as the empty string — admins overriding a field
    that's optional in the data should expect a blank rather than the
    literal text "None".
    """
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)  # leave literal {key}
        raw = values[key]
        if raw is None:
            return ""
        text = str(raw)
        if key in _URL_VARS:
            return text  # caller-supplied URL; assume already safe
        return html.escape(text, quote=True)

    return _PLACEHOLDER_RE.sub(_replace, template_text)


async def get_override(
    db: AsyncSession, user_id: uuid.UUID, template_key: str
) -> Optional[EmailTemplateOverride]:
    """Return the EmailTemplateOverride row for (user_id, template_key)
    or None. Public so admin endpoints can fetch + edit overrides."""
    if template_key not in TEMPLATES:
        return None
    row = await db.execute(
        select(EmailTemplateOverride).where(
            EmailTemplateOverride.user_id == user_id,
            EmailTemplateOverride.template_key == template_key,
        )
    )
    return row.scalar_one_or_none()


async def render_email(
    db: AsyncSession,
    template_key: str,
    user_id: uuid.UUID | None,
    **variables: Any,
) -> tuple[str, str]:
    """Render an email for (template_key, user_id).

    Returns ``(subject, html_body)``. If ``user_id`` is None or no
    override exists, falls back to the system Jinja2 template +
    schema-default subject.

    The system fallback renders ``<template_key>.html`` via the existing
    Jinja2 environment in ``email.service``. The override path uses
    flat ``{placeholder}`` substitution exclusively — see module
    docstring for the rationale.
    """
    from app.email.service import render_template  # avoid circular import at module load

    schema = get_schema(template_key)
    default_subject = (schema or {}).get("default_subject", template_key)
    allows_body = (schema or {}).get("allows_body_override", True)

    override: EmailTemplateOverride | None = None
    if user_id is not None:
        override = await get_override(db, user_id, template_key)

    # Subject ---------------------------------------------------------------
    subject_raw = (
        override.subject_override if override and override.subject_override
        else default_subject
    )
    # Subject is plain text (Content-Type: text/plain) so don't HTML-escape.
    # Use a simpler substitution that doesn't escape.
    def _replace_subject(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        v = variables[key]
        return "" if v is None else str(v)

    subject = _PLACEHOLDER_RE.sub(_replace_subject, subject_raw)

    # Body ------------------------------------------------------------------
    if override and override.body_override and allows_body:
        # Wrap the placeholder-substituted body in base.html via a
        # synthetic Jinja2 block. Easiest path: pass the rendered body
        # as a {content} block by using a small bridge template.
        substituted = _substitute(override.body_override, variables)
        html_body = _render_override_in_chrome(
            substituted,
            company_name=variables.get("company_name") or "Accountant",
            year=variables.get("year") or _current_year(),
            logo_url=variables.get("logo_url"),
        )
    else:
        # System Jinja2 path — the call site is responsible for passing
        # whatever the system template expects (objects, scalars, etc.).
        html_body = render_template(f"{template_key}.html", **variables)

    return subject, html_body


def _current_year() -> int:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).year


def _render_override_in_chrome(
    substituted_body: str,
    *,
    company_name: str,
    year: int,
    logo_url: str | None = None,
) -> str:
    """Wrap a placeholder-substituted body in the same base.html chrome
    the system templates use. We do this by rendering an in-memory
    Jinja2 string template that extends base.html and outputs the
    pre-substituted body via the ``safe`` filter — the body content
    has already been XSS-escaped at substitution time."""
    from app.email.service import _jinja_env

    bridge_source = (
        "{% extends 'base.html' %}{% block content %}{{ rendered | safe }}{% endblock %}"
    )
    template = _jinja_env.from_string(bridge_source)
    return template.render(
        rendered=substituted_body,
        company_name=company_name,
        year=year,
        logo_url=logo_url,
    )
