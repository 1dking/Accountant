"""The .ics ORGANIZER must be a real, monitored address.

It was hardcoded to `noreply@example.com`. Calendar clients route replies,
reschedules and cancellations to ORGANIZER, so every one of those went to a
domain nobody owns.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.scheduling.models import CalendarBooking
from app.scheduling.service import generate_ics


def _booking() -> CalendarBooking:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    return CalendarBooking(
        id=uuid.uuid4(),
        calendar_id=uuid.uuid4(),
        guest_name="Dana Guest",
        guest_email="dana@guest.com",
        start_time=start,
        end_time=start + timedelta(minutes=30),
    )


@pytest.mark.critical
def test_ics_organizer_uses_the_supplied_address():
    ics = generate_ics(_booking(), "Intro Call", "Acme Co", "hello@acme.com")

    assert "ORGANIZER;CN=Acme Co:mailto:hello@acme.com" in ics
    assert "example.com" not in ics, "the placeholder organizer must be gone"


@pytest.mark.critical
def test_ics_omits_organizer_rather_than_faking_one():
    """With no address available, leaving ORGANIZER out is correct. Emitting a
    fake one tells the client to send cancellations into the void."""
    ics = generate_ics(_booking(), "Intro Call", "Acme Co", "")

    assert "ORGANIZER" not in ics
    assert "example.com" not in ics
    # The rest of the invite must still be well-formed.
    assert "BEGIN:VEVENT" in ics and "END:VCALENDAR" in ics
    assert "ATTENDEE;CN=Dana Guest:mailto:dana@guest.com" in ics
