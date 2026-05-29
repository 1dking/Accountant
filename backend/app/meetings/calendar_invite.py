"""Calendar invite generation — .ics + add-to-calendar URLs (Commit 9).

Hand-rolled RFC 5545 iCalendar generator instead of pulling in the
`icalendar` package. The minimal VEVENT shape we need (UID, DTSTART,
DTEND, SUMMARY, DESCRIPTION, URL, ORGANIZER, ATTENDEE) is straight
text with no parser ambiguity — ~80 lines, no extra dep.

Public surface:
  build_ics(meeting, host_name, host_email, public_base_url) -> str
      Returns the .ics file body as a string. Use as bytes for SMTP
      attachment or response body for the download endpoint.

  google_calendar_url(meeting, host_email, public_base_url) -> str
      Pre-populated calendar.google.com URL — opens "Save event" form.

  outlook_calendar_url(meeting, host_email, public_base_url) -> str
      Pre-populated outlook.live.com / office.com URL.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

# Default duration when scheduled_end isn't set — 1 hour is the
# Google Meet / Calendly convention.
_DEFAULT_DURATION_MINUTES = 60


def _fold(line: str, limit: int = 73) -> str:
    """RFC 5545 line folding — long lines must be split with CRLF + space.
    Most mail clients tolerate unfolded lines, but Outlook can choke on
    >998 char lines, so we fold defensively at ~73 chars."""
    if len(line) <= limit:
        return line
    chunks = []
    while line:
        chunks.append(line[:limit])
        line = line[limit:]
        if line:
            line = " " + line  # leading space marks a continuation
    return "\r\n".join(chunks)


def _escape(value: str) -> str:
    """RFC 5545 TEXT escape — comma, semicolon, backslash, newline."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _format_utc(dt: datetime) -> str:
    """RFC 5545 UTC timestamp — YYYYMMDDTHHMMSSZ."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _meeting_url(public_base_url: str, slug: str) -> str:
    """Build the public guest-join URL the invite directs people to."""
    base = (public_base_url or "https://accountant.ocidm.io").rstrip("/")
    return f"{base}/m/{slug}"


def _resolve_end(meeting: Any) -> datetime:
    """Use scheduled_end if set, else scheduled_start + 1h. Fallback
    to now+1h if neither is set (defensive — instant meetings stamp
    scheduled_start, but legacy rows may not)."""
    if getattr(meeting, "scheduled_end", None):
        return meeting.scheduled_end
    start = getattr(meeting, "scheduled_start", None) or datetime.now(timezone.utc)
    return start + timedelta(minutes=_DEFAULT_DURATION_MINUTES)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_ics(
    meeting: Any,
    host_name: str,
    host_email: str,
    public_base_url: str,
) -> str:
    """Return the .ics body as a CRLF-delimited string.

    PRODID identifies us in the calendar event source — Google
    Calendar shows this verbatim, so keep it brand-friendly.
    """
    start = getattr(meeting, "scheduled_start", None) or datetime.now(timezone.utc)
    end = _resolve_end(meeting)
    join_url = _meeting_url(public_base_url, meeting.slug)
    title = _escape(meeting.title or "Meeting")
    description = _escape(
        (meeting.description or "")
        + ("\n\n" if meeting.description else "")
        + f"Join: {join_url}"
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OCIDM Accountant//Meeting//EN",
        "METHOD:REQUEST",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{meeting.id}@accountant.ocidm.io",
        f"DTSTAMP:{_format_utc(datetime.now(timezone.utc))}",
        f"DTSTART:{_format_utc(start)}",
        f"DTEND:{_format_utc(end)}",
        _fold(f"SUMMARY:{title}"),
        _fold(f"DESCRIPTION:{description}"),
        _fold(f"URL:{join_url}"),
        _fold(f"LOCATION:{join_url}"),
        _fold(
            f"ORGANIZER;CN={_escape(host_name)}:mailto:{host_email}"
        ),
    ]

    # ATTENDEE lines — one per participant. RSVP=TRUE keeps the calendar
    # invite-action UI live in clients that respect it (Outlook, Apple
    # Mail). Skip rows without an email (host with no guest_email).
    for p in getattr(meeting, "participants", []) or []:
        email = getattr(p, "guest_email", None)
        if not email:
            # User-id participants need a separate join via user.email
            # lookup — out of scope for the inline render. Skip for now.
            continue
        attendee_name = _escape(getattr(p, "guest_name", "") or email)
        lines.append(_fold(
            f"ATTENDEE;CN={attendee_name};RSVP=TRUE:mailto:{email}"
        ))

    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(lines)


def google_calendar_url(
    meeting: Any,
    host_email: str,
    public_base_url: str,
) -> str:
    """Pre-populated `calendar.google.com/calendar/render` URL.

    Format:
      https://calendar.google.com/calendar/render
        ?action=TEMPLATE
        &text=Meeting+Title
        &dates=YYYYMMDDTHHMMSSZ/YYYYMMDDTHHMMSSZ
        &details=Meeting+description+with+join+URL
        &location=https://accountant.ocidm.io/m/abc-defg-hij
    """
    start = getattr(meeting, "scheduled_start", None) or datetime.now(timezone.utc)
    end = _resolve_end(meeting)
    join_url = _meeting_url(public_base_url, meeting.slug)
    details = (meeting.description or "") + "\n\n" + f"Join: {join_url}"
    params = {
        "action": "TEMPLATE",
        "text": meeting.title or "Meeting",
        "dates": f"{_format_utc(start)}/{_format_utc(end)}",
        "details": details.strip(),
        "location": join_url,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def outlook_calendar_url(
    meeting: Any,
    host_email: str,
    public_base_url: str,
) -> str:
    """Pre-populated outlook.live.com deeplink for "Add to calendar".

    Outlook expects ISO-8601 (not RFC 5545's compact format) for the
    start/end and uses different param names than Google.
    """
    start = getattr(meeting, "scheduled_start", None) or datetime.now(timezone.utc)
    end = _resolve_end(meeting)
    join_url = _meeting_url(public_base_url, meeting.slug)
    details = (meeting.description or "") + "\n\n" + f"Join: {join_url}"
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": meeting.title or "Meeting",
        "startdt": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "enddt":   end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "body": details.strip(),
        "location": join_url,
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params)
