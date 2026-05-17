"""Integration-test fixtures.

The root conftest (backend/tests/conftest.py) provides:
  - test_engine + test_session (per-test SQLite-in-memory or PG)
  - async_client (HTTP client bound to the FastAPI app via ASGITransport)
  - test_user, admin_user, admin_token fixtures

This conftest adds integration-specific helpers:
  - twilio_signed_form: build a real X-Twilio-Signature header so
    signature-gated webhook tests don't have to mock the validator
  - mediarecorder_blob: the actual byte stream a browser MediaRecorder
    produces for audio/webm;codecs=opus uploads
"""
import os
from typing import Callable

import pytest


@pytest.fixture
def twilio_signed_form() -> Callable[[str, dict], dict]:
    """Return a builder that produces (url, params, signature_header).

    Usage in tests:
        url, params, sig = twilio_signed_form(
            "https://accountant.ocidm.io/api/communication/sms/webhook",
            {"From": "+12896984168", "To": "+13659092096", "Body": "hi"},
        )
        resp = await client.post(
            "/api/communication/sms/webhook",
            data=params,
            headers={
                "X-Twilio-Signature": sig,
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "accountant.ocidm.io",
            },
        )
    """
    from twilio.request_validator import RequestValidator

    # The webhook handler reads settings.twilio_auth_token from
    # request.app.state.settings, NOT from a fresh Settings(). Tests
    # must override this — easiest path is to set a deterministic
    # token on the app state in the test setup.
    test_token = os.environ.get("TEST_TWILIO_AUTH_TOKEN", "test-twilio-auth-token")

    def _build(url: str, params: dict) -> tuple[str, dict, str]:
        validator = RequestValidator(test_token)
        signature = validator.compute_signature(url, params)
        return url, params, signature

    return _build


# Path to the fixtures folder
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
