"""Meeting invite email sender (Commit 9).

Best-effort: failures NEVER block create_meeting. Logs loudly so the
host can re-send manually via POST /meetings/{id}/send-invites.

Public surface:
  send_meeting_invites(db, meeting, user, settings)
      Pulls participant_emails off the meeting, generates a single
      .ics attachment + a friendly HTML body with the slug URL + add-
      to-calendar buttons (rendered as plain links — most mail clients
      strip <button> CSS), sends to each invitee in parallel.

  build_invite_body(meeting, host_name, host_email, public_base_url)
      Returns the rendered HTML body string. Unit-tested separately.
"""
from __future__ import annotations

import asyncio
import logging
from html import escape as html_escape
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branding.service import get_public_branding
from app.config import Settings
from app.email.service import resolve_smtp_config, send_email
from app.meetings.calendar_invite import (
    build_ics, google_calendar_url, outlook_calendar_url,
)
from app.meetings.models import Meeting
from app.settings.service import get_company_settings

logger = logging.getLogger(__name__)


async def _load_brand(db: AsyncSession) -> dict:
    """Pull logo / brand color / company name for the email render.

    Falls back to OCIDM defaults so the template never breaks if the
    user hasn't configured anything yet.
    """
    brand = {
        "logo_url": None,
        "primary_color": "#4f46e5",
        "company_name": "OCIDM Accountant",
        "header_html": None,
        "footer_html": None,
    }
    try:
        b = await get_public_branding(db)
        if b is not None:
            brand["logo_url"] = b.logo_image_url or b.logo_url or None
            if b.primary_color:
                brand["primary_color"] = b.primary_color
            brand["header_html"] = b.email_header_html or None
            brand["footer_html"] = b.email_footer_html or None
        cs = await get_company_settings(db)
        if cs is not None and cs.company_name:
            brand["company_name"] = cs.company_name
    except Exception as exc:
        logger.warning("meeting.invite_branding_load_failed err=%s", str(exc)[:200])
    return brand


async def build_invite_body(
    meeting: Any,
    host_name: str,
    host_email: str,
    public_base_url: str,
    db: AsyncSession | None = None,
) -> str:
    """HTML body for the invite email. Keep CSS inline + minimal —
    Gmail / Outlook / Apple Mail strip most stylesheets."""
    base = (public_base_url or "https://accountant.ocidm.io").rstrip("/")
    join_url = f"{base}/m/{meeting.slug}"
    g_url = google_calendar_url(meeting, host_email, public_base_url)
    o_url = outlook_calendar_url(meeting, host_email, public_base_url)
    title = html_escape(meeting.title or "Meeting")
    host = html_escape(host_name or host_email)
    description_html = ""
    if meeting.description:
        description_html = (
            f'<p style="margin: 0 0 16px; color:#374151;">'
            f'{html_escape(meeting.description)}</p>'
        )
    when_html = ""
    if meeting.scheduled_start:
        when_html = (
            f'<p style="margin: 0 0 16px; color:#374151;">'
            f'<strong>When:</strong> '
            f'{meeting.scheduled_start.strftime("%A, %B %d at %I:%M %p UTC")}</p>'
        )

    brand = await _load_brand(db) if db is not None else {
        "logo_url": None, "primary_color": "#4f46e5",
        "company_name": "OCIDM Accountant",
        "header_html": None, "footer_html": None,
    }
    brand_color = brand["primary_color"] or "#4f46e5"
    company_name = html_escape(brand["company_name"] or "OCIDM Accountant")
    logo_html = ""
    if brand["logo_url"]:
        logo_html = (
            f'<img src="{html_escape(brand["logo_url"])}" alt="{company_name}" '
            f'style="max-height:40px;margin:0 0 18px;display:block;" />'
        )
    header_html = brand["header_html"] or ""
    footer_html = brand["footer_html"] or ""

    return f"""<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;background:#f9fafb;padding:24px;margin:0;">
  {header_html}
  <table cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
    <tr><td style="padding:32px 32px 24px;">
      {logo_html}
      <h1 style="margin:0 0 6px;color:#111827;font-size:20px;font-weight:600;">{title}</h1>
      <p style="margin:0 0 20px;color:#6b7280;font-size:13px;">Invited by {host}</p>
      {when_html}
      {description_html}
      <a href="{html_escape(join_url)}" style="display:inline-block;padding:12px 24px;background:{brand_color};color:#ffffff;font-weight:600;font-size:14px;text-decoration:none;border-radius:8px;margin:8px 0 24px;">Join meeting</a>
      <p style="margin:0 0 8px;color:#6b7280;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Add to your calendar</p>
      <p style="margin:0 0 16px;font-size:13px;">
        <a href="{html_escape(g_url)}" style="color:{brand_color};text-decoration:none;margin-right:14px;">Google Calendar</a>
        <a href="{html_escape(o_url)}" style="color:{brand_color};text-decoration:none;margin-right:14px;">Outlook</a>
        <span style="color:#9ca3af;">(.ics file attached)</span>
      </p>
      <p style="margin:24px 0 0;padding-top:16px;border-top:1px solid #f3f4f6;color:#9ca3af;font-size:11px;">
        Powered by {company_name}. The meeting link only works for invited email addresses.
      </p>
    </td></tr>
  </table>
  {footer_html}
</body></html>"""


async def send_meeting_invites(
    db: AsyncSession,
    meeting: Meeting,
    user: User,
    settings: Settings,
    *,
    recipients: list[str] | None = None,
) -> dict:
    """Send the invite email to every participant_email on the meeting.

    Returns {"sent": int, "failed": int, "errors": [str]} so callers can
    surface partial-success state (e.g. "Sent to 3 of 4 invitees").
    Per-recipient failures are logged but don't abort the whole batch.

    recipients: override to re-send to a subset (e.g. one specific
    address). When omitted, sends to all participant_emails on the
    meeting's participants list.
    """
    addresses = recipients
    if addresses is None:
        addresses = [
            p.guest_email for p in (meeting.participants or [])
            if p.guest_email
        ]
    addresses = list(dict.fromkeys(a.strip() for a in addresses if a and a.strip()))

    if not addresses:
        return {"sent": 0, "failed": 0, "errors": []}

    try:
        smtp_config = await resolve_smtp_config(db, user)
    except Exception as exc:
        logger.warning(
            "meeting.invite_send_skipped meeting_id=%s reason=no_smtp err=%s",
            meeting.id, str(exc)[:200],
        )
        return {"sent": 0, "failed": len(addresses), "errors": ["No SMTP configured"]}

    host_name = user.full_name or user.email
    host_email = user.email
    public_base_url = settings.public_base_url

    ics_body = build_ics(meeting, host_name, host_email, public_base_url)
    ics_bytes = ics_body.encode("utf-8")
    attachments = [("meeting.ics", ics_bytes, "text/calendar")]
    html_body = await build_invite_body(
        meeting, host_name, host_email, public_base_url, db=db,
    )
    subject = f"Invitation: {meeting.title}"

    async def _one(addr: str) -> tuple[str, Exception | None]:
        try:
            await send_email(
                smtp_config, addr, subject, html_body, attachments=attachments,
            )
            return (addr, None)
        except Exception as exc:
            return (addr, exc)

    results = await asyncio.gather(*[_one(a) for a in addresses])
    sent = 0
    failed = 0
    errors: list[str] = []
    for addr, err in results:
        if err is None:
            sent += 1
        else:
            failed += 1
            errors.append(f"{addr}: {str(err)[:200]}")
            logger.warning(
                "meeting.invite_send_failed meeting_id=%s to=%s err=%s",
                meeting.id, addr, str(err)[:200],
            )

    logger.info(
        "meeting.invites_sent meeting_id=%s sent=%d failed=%d",
        meeting.id, sent, failed,
    )
    return {"sent": sent, "failed": failed, "errors": errors}
