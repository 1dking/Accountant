"""Bug #3 regression: <audio> playback needs ?token= query param auth.

Symptom (2026-05-16): native <audio src=…> elements can't send
Authorization: Bearer headers. /calls/{id}/recording returned 401.
Fix was to switch the dependency from get_current_user to
get_current_user_or_token (existing helper that accepts ?token= as
alternative to Bearer header).

This test asserts the dependency is in the right shape — it doesn't
hit the live endpoint (that requires DB+Twilio fixtures), it asserts
the dependency is wired to the query-token helper.
"""
import inspect

from app.communication import router as comm_router
from app.dependencies import get_current_user, get_current_user_or_token


def test_recording_endpoint_uses_query_token_dependency():
    """The native <audio> element can't send Bearer headers — the
    recording proxy must use get_current_user_or_token (accepts both
    Bearer header AND ?token= query param)."""
    # Locate the route function on the registered router
    target_path = "/calls/{call_id}/recording"
    matching = [r for r in comm_router.router.routes if getattr(r, "path", None) == target_path]
    assert len(matching) == 1, f"expected 1 route at {target_path}, got {len(matching)}"
    route = matching[0]

    # Inspect the endpoint signature for the current_user dependency
    sig = inspect.signature(route.endpoint)
    found_query_token_dep = False
    found_bearer_only_dep = False
    for name, param in sig.parameters.items():
        if name != "current_user":
            continue
        # The Annotated metadata holds the Depends() instance — walk it
        anno = param.annotation
        for meta in getattr(anno, "__metadata__", ()):
            dep = getattr(meta, "dependency", None)
            if dep is get_current_user_or_token:
                found_query_token_dep = True
            elif dep is get_current_user:
                found_bearer_only_dep = True

    assert found_query_token_dep, (
        "stream_call_recording must depend on get_current_user_or_token "
        "so the native <audio> element can authenticate via ?token= query param. "
        "Currently using a Bearer-only dependency, which 401s for <audio src>."
    )
    assert not found_bearer_only_dep, (
        "stream_call_recording is wired to Bearer-only auth — <audio> "
        "playback will 401. Switch to get_current_user_or_token."
    )
