"""Bug #1 regression #2: Twilio webhook signature verification.

Symptom (2026-05-15 voice debug): the verified_twilio_form dependency
reconstructed URLs incorrectly behind Cloudflare+Apache, causing 403
on every signed Twilio webhook. Fix was to consult X-Forwarded-Proto
and X-Forwarded-Host headers when reconstructing the signed URL.

This test exercises the URL-reconstruction logic in isolation.
"""
from twilio.request_validator import RequestValidator

TEST_TOKEN = "test-twilio-auth-token-deterministic"


def reconstruct_signed_url(
    scheme: str,
    host: str,
    path: str,
    query: str = "",
    forwarded_proto: str | None = None,
    forwarded_host: str | None = None,
) -> str:
    """Mirrors the production logic in verified_twilio_form."""
    proto = forwarded_proto or scheme
    h = forwarded_host or host
    url = f"{proto}://{h}{path}"
    if query:
        url += f"?{query}"
    return url


class TestSignatureUrlReconstruction:
    def test_uses_forwarded_headers_when_present(self):
        """Cloudflare/Apache forward proto+host — production URL must
        match the URL Twilio actually signed."""
        url = reconstruct_signed_url(
            scheme="http",  # Internal uvicorn sees http
            host="0.0.0.0:8000",
            path="/api/communication/sms/webhook",
            forwarded_proto="https",
            forwarded_host="accountant.ocidm.io",
        )
        assert url == "https://accountant.ocidm.io/api/communication/sms/webhook"

    def test_falls_back_to_raw_when_no_forwarded(self):
        """Local-dev path — no Cloudflare in front."""
        url = reconstruct_signed_url(
            scheme="http",
            host="localhost:8000",
            path="/api/communication/sms/webhook",
        )
        assert url == "http://localhost:8000/api/communication/sms/webhook"

    def test_signature_validates_with_correct_url(self):
        """End-to-end: sign + verify a fake webhook payload."""
        validator = RequestValidator(TEST_TOKEN)
        url = "https://accountant.ocidm.io/api/communication/sms/webhook"
        params = {"From": "+12896984168", "To": "+13659092096", "Body": "hi"}
        sig = validator.compute_signature(url, params)
        assert validator.validate(url, params, sig)

    def test_signature_rejects_wrong_url(self):
        """Using the wrong URL (e.g., internal http://0.0.0.0:8000)
        causes validation to fail — this is exactly the production bug."""
        validator = RequestValidator(TEST_TOKEN)
        signed_url = "https://accountant.ocidm.io/api/communication/sms/webhook"
        wrong_url = "http://0.0.0.0:8000/api/communication/sms/webhook"
        params = {"From": "+12896984168"}
        sig = validator.compute_signature(signed_url, params)
        # validate with wrong URL → should be False (this was the bug)
        assert not validator.validate(wrong_url, params, sig)
