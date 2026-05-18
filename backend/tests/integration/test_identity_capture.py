"""Identity capture flow — extraction logic + state machine.

These are unit-level tests on the helpers (pure-function inputs +
deterministic state transitions) without exercising the live Twilio
or Anthropic clients. End-to-end is verified via smoke against the
deployed system.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.communication.identity_capture import (
    IdentityCaptureAttempt,
    MAX_ATTEMPTS_PER_7_DAYS,
    determine_state,
    is_rate_limited,
)


def _make_attempt(
    *,
    attempt_count: int = 1,
    asked_at: datetime | None = None,
    answered_at: datetime | None = None,
    contact_created_id=None,
    last_attempt_at: datetime | None = None,
) -> IdentityCaptureAttempt:
    """Build a detached IdentityCaptureAttempt for state-machine assertions.

    Not persisted — we're testing pure-function transitions.
    """
    return IdentityCaptureAttempt(
        phone_number="+12896984168",
        user_id=None,  # type: ignore — fine for in-memory state tests
        first_inbound_at=datetime.now(timezone.utc),
        asked_at=asked_at,
        answered_at=answered_at,
        contact_created_id=contact_created_id,
        attempt_count=attempt_count,
        last_attempt_at=last_attempt_at or datetime.now(timezone.utc),
    )


class TestRateLimit:
    def test_under_cap_not_limited(self):
        a = _make_attempt(attempt_count=1)
        assert not is_rate_limited(a)

    def test_at_cap_within_window_limited(self):
        a = _make_attempt(
            attempt_count=MAX_ATTEMPTS_PER_7_DAYS,
            last_attempt_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        assert is_rate_limited(a)

    def test_at_cap_outside_window_not_limited(self):
        a = _make_attempt(
            attempt_count=MAX_ATTEMPTS_PER_7_DAYS,
            last_attempt_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        assert not is_rate_limited(a)

    def test_already_answered_never_limited(self):
        """Resolved attempts shouldn't gate retries — but state machine
        should treat them as 'succeeded' anyway, not 'exhausted'."""
        a = _make_attempt(
            attempt_count=MAX_ATTEMPTS_PER_7_DAYS,
            answered_at=datetime.now(timezone.utc),
            last_attempt_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert not is_rate_limited(a)


class TestStateMachine:
    def test_brand_new_attempt_is_first_contact(self):
        a = _make_attempt(attempt_count=0, asked_at=None)
        assert determine_state(a, just_created=True) == "first_contact"

    def test_asked_but_no_answer_is_expecting_answer(self):
        a = _make_attempt(
            attempt_count=1,
            asked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert determine_state(a, just_created=False) == "expecting_answer"

    def test_contact_created_is_succeeded(self):
        import uuid

        a = _make_attempt(
            attempt_count=1,
            asked_at=datetime.now(timezone.utc),
            answered_at=datetime.now(timezone.utc),
            contact_created_id=uuid.uuid4(),
        )
        assert determine_state(a, just_created=False) == "succeeded"

    def test_two_failed_attempts_within_week_is_exhausted(self):
        a = _make_attempt(
            attempt_count=MAX_ATTEMPTS_PER_7_DAYS,
            asked_at=datetime.now(timezone.utc) - timedelta(days=1),
            last_attempt_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert determine_state(a, just_created=False) == "exhausted"


class TestOutboundCopy:
    """Sanity-check that the canned messages are sane sizes for SMS."""

    def test_first_ask_under_320_chars(self):
        from app.communication.identity_capture import FIRST_ASK

        assert 0 < len(FIRST_ASK) <= 320

    def test_clarify_under_320_chars(self):
        from app.communication.identity_capture import CLARIFY_ASK

        assert 0 < len(CLARIFY_ASK) <= 320

    def test_confirmation_template_renders(self):
        from app.communication.identity_capture import CONFIRMATION_TEMPLATE

        rendered = CONFIRMATION_TEMPLATE.format(name="Sarah")
        assert "Sarah" in rendered
        assert len(rendered) <= 320
