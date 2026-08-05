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
    ("POST", "/api/auth/password-reset/request"),
    ("POST", "/api/auth/password-reset/confirm"),

    # Notifications
    ("GET", "/api/notifications/unread-count"),
    ("PUT", "/api/notifications/{notification_id}/read"),
    ("PUT", "/api/notifications/read-all"),
    ("GET", "/api/notifications/preferences"),
    ("PUT", "/api/notifications/preferences"),

    # Email template overrides
    ("GET", "/api/email/templates"),
    ("GET", "/api/email/templates/{template_key}"),
    ("PUT", "/api/email/templates/{template_key}"),
    ("DELETE", "/api/email/templates/{template_key}"),
    ("POST", "/api/email/templates/{template_key}/test"),

    # Email absorption (Session E)
    ("POST", "/api/communication/email-absorb"),
    ("GET", "/api/communication/email-absorb/runs"),
    ("GET", "/api/communication/email-absorb/runs/{run_id}"),

    # Voicemail orphan recovery (admin-only manual trigger)
    ("POST", "/api/platform-admin/voicemails/recover-orphans"),

    # Pages v2 — conversational PRD-first generation (Session 1)
    ("POST", "/api/pages/ai/sessions"),
    ("GET", "/api/pages/ai/sessions/{session_id}"),
    ("POST", "/api/pages/ai/sessions/{session_id}/prompt"),
    ("POST", "/api/pages/ai/sessions/{session_id}/approve"),
    ("POST", "/api/pages/ai/sessions/{session_id}/generate"),
    ("POST", "/api/pages/{page_id}/sections/{section_index}/refine"),

    # Pages v2 — static publish (Session 2)
    ("POST", "/api/pages/{page_id}/publish-static"),
    ("GET", "/api/pages/p/{slug}"),

    # Stripe Connect
    ("GET", "/api/integrations/stripe-connect/connect"),
    ("GET", "/api/integrations/stripe-connect/status"),
    ("DELETE", "/api/integrations/stripe-connect/disconnect"),
]


@pytest.fixture(scope="module")
def registered_routes() -> set[tuple[str, str]]:
    """Return {(METHOD, path)} for every route the app registers.

    Source of truth is the OpenAPI spec (``app.openapi()``), NOT a manual walk
    of ``app.routes``.

    Why this changed: Starlette's lazy include (the ``_IncludedRouter`` node,
    shipped in the 1.x line we now run in prod and CI) stopped *flattening*
    ``include_router()`` sub-routers into ``app.routes``. A sub-router now shows
    up as ONE opaque node with ``path=None``, so a flat top-level walk sees only
    the app's directly-decorated routes (``/api/system/health``, ``/docs``,
    ``/.well-known/...``) and misses every ``include_router()`` path — i.e. all
    ~350 feature endpoints. The routes are still registered and served correctly
    (prod works; the live HTTP api-tests pass); only the *walk* went blind, which
    is why this test passed on an older local Starlette and failed in CI.

    The OpenAPI generator traverses the nested router tree correctly, so it
    enumerates the same routes on both the old (flat) and new (nested) Starlette.
    An earlier note here claimed ``openapi()`` tripped on Request forward-refs;
    that is no longer true on the current FastAPI/Pydantic (verified against both
    the old and new dependency sets). The test stays meaningful: a genuinely
    missing or renamed route is absent from the spec and still fails loudly.
    """
    app = create_app()
    spec = app.openapi()
    routes: set[tuple[str, str]] = set()
    for path, operations in spec.get("paths", {}).items():
        for method in operations:
            m = method.upper()
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
