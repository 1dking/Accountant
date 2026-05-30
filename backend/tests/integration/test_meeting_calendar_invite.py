"""Commit 9 — calendar invite (.ics + add-to-calendar URLs + email send).

Covers:
  - build_ics: VCALENDAR shell + VEVENT shape with UID, DTSTART, DTEND,
    SUMMARY, DESCRIPTION, URL, ORGANIZER, ATTENDEE lines
  - build_ics: TEXT-field escaping (comma, semicolon, newline)
  - google_calendar_url / outlook_calendar_url: correct base + params
  - build_invite_body: HTML body contains join URL + add-to-calendar
    links + meeting title
  - send_meeting_invites: 0 sent when no participants (no SMTP call)
  - send_meeting_invites: returns errors per address, doesn't raise
  - create_meeting with create_calendar_event=True is best-effort —
    SMTP failure does NOT roll back the meeting creation
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import service
from app.meetings.calendar_invite import (
    build_ics, google_calendar_url, outlook_calendar_url,
)
from app.meetings.email_invite import build_invite_body, send_meeting_invites
from app.meetings.models import Meeting, MeetingStatus
from app.meetings.schemas import MeetingCreate
from tests.conftest import TEST_SETTINGS


@pytest_asyncio.fixture
async def settings_with_base():
    return TEST_SETTINGS.model_copy(update={
        "public_base_url": "https://accountant.ocidm.io",
        "livekit_url": "wss://example.livekit.cloud",
        "livekit_api_key": "lk-test-key",
        "livekit_api_secret": "lk-test-secret-thirtytwobyteminkeylength",
    })


@pytest_asyncio.fixture
async def host_user(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="alice.host@example.com",
        hashed_password=hash_password("x"),
        full_name="Alice Host", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def scheduled_meeting(
    db: AsyncSession, host_user: User, settings_with_base,
) -> Meeting:
    data = MeetingCreate(
        title="Q3 Cash flow review",
        description="Walk through last quarter; identify levers for Q4.",
        scheduled_start=datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc),
        participant_emails=["client1@acme.com", "client2@acme.com"],
        create_calendar_event=False,  # avoid auto-send during fixture setup
    )
    return await service.create_meeting(db, host_user, data, settings_with_base)


# ---------------------------------------------------------------------------
# .ics generation
# ---------------------------------------------------------------------------


def test_build_ics_has_vcalendar_and_vevent_shell(scheduled_meeting):
    ics = build_ics(
        scheduled_meeting, "Alice Host", "alice.host@example.com",
        "https://accountant.ocidm.io",
    )
    assert "BEGIN:VCALENDAR" in ics
    assert "VERSION:2.0" in ics
    assert "PRODID:" in ics
    assert "BEGIN:VEVENT" in ics
    assert "END:VEVENT" in ics
    assert "END:VCALENDAR" in ics


def test_build_ics_carries_uid_summary_url(scheduled_meeting):
    ics = build_ics(
        scheduled_meeting, "Alice Host", "alice.host@example.com",
        "https://accountant.ocidm.io",
    )
    assert f"UID:{scheduled_meeting.id}@accountant.ocidm.io" in ics
    # SUMMARY may be folded; just check the title appears
    assert "Q3 Cash flow review" in ics
    # URL points at the public slug page
    assert f"https://accountant.ocidm.io/m/{scheduled_meeting.slug}" in ics


def test_build_ics_dtstart_dtend_in_utc(scheduled_meeting):
    ics = build_ics(
        scheduled_meeting, "Alice", "alice@example.com",
        "https://accountant.ocidm.io",
    )
    # Compact UTC timestamp per RFC 5545
    assert "DTSTART:20260615T140000Z" in ics
    assert "DTEND:20260615T150000Z" in ics


def test_build_ics_escapes_text_special_chars(host_user, settings_with_base, db):
    """Comma, semicolon, backslash, newline must be escaped in TEXT
    fields per RFC 5545."""
    import asyncio
    data = MeetingCreate(
        title="Strategy, planning; Q4",
        description="Topics:\n- pricing\n- staffing",
        scheduled_start=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        create_calendar_event=False,
    )
    m = asyncio.get_event_loop().run_until_complete(
        service.create_meeting(db, host_user, data, settings_with_base)
    ) if False else None
    # Simpler — use a stub Meeting-shape object
    class _Stub:
        id = uuid.uuid4()
        slug = "abc-defg-hij"
        title = "Strategy, planning; Q4"
        description = "Topics:\n- pricing"
        scheduled_start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
        scheduled_end = None
        participants = []
    ics = build_ics(_Stub(), "H", "h@x.com", "https://accountant.ocidm.io")
    assert "Strategy\\, planning\\; Q4" in ics
    assert "\\n- pricing" in ics or "\\n" in ics


def test_build_ics_includes_attendee_line_per_invitee(scheduled_meeting):
    ics = build_ics(
        scheduled_meeting, "Alice", "alice@example.com",
        "https://accountant.ocidm.io",
    )
    # Both invitees in the schedule fixture should appear
    assert "mailto:client1@acme.com" in ics
    assert "mailto:client2@acme.com" in ics


# ---------------------------------------------------------------------------
# Add-to-calendar URLs
# ---------------------------------------------------------------------------


def test_google_calendar_url_template_with_params(scheduled_meeting):
    url = google_calendar_url(
        scheduled_meeting, "alice@example.com",
        "https://accountant.ocidm.io",
    )
    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    # Compact UTC dates joined with "/"
    assert "dates=20260615T140000Z%2F20260615T150000Z" in url
    # Title in query
    assert "Q3+Cash+flow+review" in url or "Q3%20Cash%20flow%20review" in url


def test_outlook_calendar_url_compose_with_params(scheduled_meeting):
    url = outlook_calendar_url(
        scheduled_meeting, "alice@example.com",
        "https://accountant.ocidm.io",
    )
    assert url.startswith("https://outlook.live.com/calendar/0/deeplink/compose?")
    assert "rru=addevent" in url
    # ISO-8601 (not RFC 5545 compact form) for Outlook
    assert "startdt=2026-06-15T14%3A00%3A00Z" in url


# ---------------------------------------------------------------------------
# Email body
# ---------------------------------------------------------------------------


async def test_build_invite_body_contains_join_url_and_calendar_links(scheduled_meeting):
    # db omitted → render falls back to OCIDM defaults (no brand row).
    html = await build_invite_body(
        scheduled_meeting, "Alice Host", "alice@example.com",
        "https://accountant.ocidm.io",
    )
    assert f"https://accountant.ocidm.io/m/{scheduled_meeting.slug}" in html
    assert "calendar.google.com/calendar/render" in html
    assert "outlook.live.com" in html
    assert "Q3 Cash flow review" in html
    assert "Alice Host" in html


# ---------------------------------------------------------------------------
# send_meeting_invites
# ---------------------------------------------------------------------------


async def test_send_invites_no_participants_returns_zero(
    db: AsyncSession, host_user: User, settings_with_base,
):
    """Meeting with no participant_emails: send returns {sent:0,
    failed:0}, doesn't try to resolve SMTP, doesn't raise."""
    data = MeetingCreate(
        title="Solo prep",
        scheduled_start=datetime.now(timezone.utc),
        participant_emails=[],
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host_user, data, settings_with_base)
    result = await send_meeting_invites(db, meeting, host_user, settings_with_base)
    assert result == {"sent": 0, "failed": 0, "errors": []}


async def test_send_invites_no_smtp_returns_failed_no_raise(
    db: AsyncSession, host_user: User,
    scheduled_meeting: Meeting, settings_with_base,
):
    """No SMTP configured: send returns failed=N with error message,
    doesn't raise. Lets the host see in the UI that delivery didn't
    happen + configure SMTP, then re-send."""
    # No SmtpConfig rows in the test DB
    result = await send_meeting_invites(
        db, scheduled_meeting, host_user, settings_with_base,
    )
    assert result["sent"] == 0
    assert result["failed"] == 2
    assert "No SMTP configured" in result["errors"][0]


async def test_create_meeting_invite_failure_does_not_roll_back(
    db: AsyncSession, host_user: User, settings_with_base,
):
    """Best-effort delivery — invite send failure (no SMTP) must NOT
    roll back the meeting itself. The host can re-send manually later."""
    data = MeetingCreate(
        title="Client call",
        scheduled_start=datetime.now(timezone.utc),
        participant_emails=["client@acme.com"],
        create_calendar_event=True,  # triggers the auto-send path
    )
    meeting = await service.create_meeting(db, host_user, data, settings_with_base)
    # Meeting persisted despite SMTP-not-configured invite failure
    assert meeting.id is not None
    assert meeting.slug is not None
    assert meeting.title == "Client call"
