"""Notification preferences — default resolution + label coverage.

State machine + Twilio send are tested separately via the deployed
system. These unit tests cover the pure helpers + ensure every known
notification_type has both a default and a human-readable label.
"""
from app.notifications.service import (
    DEFAULT_PREFERENCES,
    NOTIFICATION_TYPE_LABELS,
)


class TestDefaultsCoverage:
    """Every notification_type emitted by the system must have an entry
    in BOTH DEFAULT_PREFERENCES and NOTIFICATION_TYPE_LABELS. This
    catches "added a new type but forgot to register it" drift."""

    KNOWN_TYPES = {
        "sms_inbound",
        "voicemail_received",
        "ai_reply_sent",
        "automation_flow_completed",
        "admin_reminder",
        "identity_capture_asked",
        "contact_auto_created",
        "identity_capture_failed",
        "password_changed",
    }

    def test_every_known_type_has_default(self):
        for t in self.KNOWN_TYPES:
            assert t in DEFAULT_PREFERENCES, (
                f"Notification type {t!r} is emitted by the system but has "
                f"no entry in DEFAULT_PREFERENCES. Add one to "
                f"app/notifications/service.py."
            )

    def test_every_known_type_has_label(self):
        for t in self.KNOWN_TYPES:
            assert t in NOTIFICATION_TYPE_LABELS, (
                f"Notification type {t!r} has no human-readable label. "
                f"Add one to NOTIFICATION_TYPE_LABELS so the Settings UI "
                f"can render it."
            )

    def test_fallback_default_exists(self):
        """New notification types added at runtime hit this fallback."""
        assert "_default" in DEFAULT_PREFERENCES
        d = DEFAULT_PREFERENCES["_default"]
        assert d["in_app"] is True
        assert d["email"] is False
        assert d["sms"] is False

    def test_high_urgency_defaults_sms_on(self):
        """Voicemail + identity-capture-failed are high-urgency types
        that default to interrupting via SMS (when fallback_phone is set).
        Documenting this here so a future shuffle of defaults doesn't
        silently downgrade urgency."""
        assert DEFAULT_PREFERENCES["voicemail_received"]["sms"] is True
        assert DEFAULT_PREFERENCES["identity_capture_failed"]["sms"] is True

    def test_low_urgency_defaults_sms_off(self):
        """Routine events shouldn't buzz the user's cell by default."""
        for t in ("sms_inbound", "ai_reply_sent", "automation_flow_completed"):
            assert DEFAULT_PREFERENCES[t]["sms"] is False, (
                f"{t} should default to SMS off — it's a routine event"
            )
