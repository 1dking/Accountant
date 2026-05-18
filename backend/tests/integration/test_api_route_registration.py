"""Bug #5 regression: frontend API client URLs must match backend routes.

Symptom (2026-05-17): /api/communication/sms (frontend) vs
/api/communication/sms/send (backend). FastAPI returned 405 because
the path existed at GET, not POST. Took until live test to surface.

This test parses the OpenAPI spec from the live app and checks a
list of known-good API client paths against what's registered.

Whitelist approach (rather than parsing frontend TS files): we
explicitly enumerate the paths the frontend depends on, so the test
fails CLEARLY when one drifts. Future: auto-extract from
frontend/src/api/*.ts via a sibling script.
"""
import pytest

from app.main import create_app


# Paths the frontend depends on. (method, path) pairs.
# Path templates use {param} matching FastAPI's openapi format.
FRONTEND_API_DEPENDENCIES = [
    # Communication
    ("POST", "/api/communication/sms/send"),
    ("GET", "/api/communication/sms"),
    ("GET", "/api/communication/calls"),
    ("GET", "/api/communication/calls/{call_id}/recording"),
    ("GET", "/api/communication/phone-numbers"),
    ("POST", "/api/communication/phone-numbers/{phone_id}/sync-webhooks"),
    ("POST", "/api/communication/twilio/purchase"),
    ("GET", "/api/communication/automation-flows"),
    ("POST", "/api/communication/automation-flows"),
    ("PUT", "/api/communication/automation-flows/{flow_id}"),
    ("DELETE", "/api/communication/automation-flows/{flow_id}"),

    # Contacts
    ("GET", "/api/contacts/{contact_id}/conversations"),
    ("GET", "/api/contacts/{contact_id}/memories"),
    ("POST", "/api/contacts/{contact_id}/memories"),
    ("GET", "/api/contacts/{contact_id}/brief"),
    ("POST", "/api/contacts/{contact_id}/brief/regenerate"),
    ("PUT", "/api/contacts/{contact_id}/conversation-engine"),

    # Auth
    ("PUT", "/api/auth/me"),
    ("GET", "/api/auth/me/voicemail-greeting"),
    ("POST", "/api/auth/me/voicemail-greeting"),
    ("DELETE", "/api/auth/me/voicemail-greeting"),

    # Notifications
    ("GET", "/api/notifications/unread-count"),
    ("PUT", "/api/notifications/{notification_id}/read"),
    ("PUT", "/api/notifications/read-all"),
    ("GET", "/api/notifications/preferences"),
    ("PUT", "/api/notifications/preferences"),
]


@pytest.fixture(scope="module")
def registered_routes() -> set[tuple[str, str]]:
    """Return {(METHOD, path)} by walking app.routes directly.

    Avoids app.openapi() because that triggers a full Pydantic schema
    generation pass which trips on Request forward-refs in some
    dependency annotations. We only need (method, path) — APIRoute
    objects already expose both.
    """
    app = create_app()
    routes: set[tuple[str, str]] = set()
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        for m in methods:
            if m in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                routes.add((m, path))
    return routes


@pytest.mark.parametrize("method,path", FRONTEND_API_DEPENDENCIES)
def test_frontend_api_dependency_registered(
    method: str, path: str, registered_routes: set[tuple[str, str]]
):
    """For every (method, path) the frontend depends on, assert it's
    registered on the backend. Catches sendSms() → /sms (missing /send)
    style typos at test time, not in production."""
    assert (method, path) in registered_routes, (
        f"Frontend expects {method} {path} but backend doesn't register it. "
        f"Most likely cause: someone renamed the route OR the frontend "
        f"client typoed the URL. Check frontend/src/api/*.ts vs the "
        f"@router decorators."
    )
