"""Does a created account get MORE features than the admin selected?

The admin UI sends the FULL feature grid, so the happy path is fine. These tests
probe what happens when the submitted selection is INCOMPLETE — which happens
when a client sends a partial map, or (more likely) when a stale cached frontend
bundle submits a grid from before a new feature key was added to the backend.

resolve_feature_access() merges the selection over ROLE_DEFAULTS, so any feature
the selection does not mention keeps its role default — and team_member/manager
default to ALL features true. That is fail-OPEN.
"""

import json

import pytest
from sqlalchemy import select

from app.auth.features import ALL_FEATURES, resolve_feature_access
from app.auth.models import Role, User
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Pure resolver behaviour (no HTTP) — the core semantics
# ---------------------------------------------------------------------------

def test_partial_selection_leaks_role_defaults():
    """A partial selection must not silently grant everything else."""
    selected = {"contacts": True}  # admin picked exactly ONE module
    effective = resolve_feature_access("team_member", json.dumps(selected))
    granted = sorted(f for f, on in effective.items() if on)
    extra = [f for f in granted if f not in selected]
    assert extra == [], (
        f"Selected {sorted(selected)} but account also received {len(extra)} "
        f"un-selected features: {extra}"
    )


def test_missing_key_from_stale_grid_is_not_granted():
    """Simulate a stale frontend bundle: full grid minus one newly-added key."""
    full_grid = {f: False for f in ALL_FEATURES}
    full_grid["contacts"] = True
    newest = "meeting_rooms"  # stand-in for "a key the old bundle didn't know"
    stale_grid = {k: v for k, v in full_grid.items() if k != newest}

    effective = resolve_feature_access("team_member", json.dumps(stale_grid))
    assert effective[newest] is False, (
        f"'{newest}' was absent from the submitted grid and was granted anyway "
        "(fell back to the role default)"
    )


def test_client_role_is_closed_by_default():
    """Regression guard: the client role must stay all-false by default."""
    effective = resolve_feature_access("client", None)
    assert not any(effective.values()), "client role granted features by default"


# ---------------------------------------------------------------------------
# End-to-end through the real admin API + the module gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_created_account_cannot_open_unselected_module(client, admin_user, db):
    """Create an account granting ONLY contacts, then try a module we did not
    grant. The gate must refuse."""
    r = await client.post(
        "/api/auth/users",
        headers=auth_header(admin_user),
        json={
            "email": "scoped-client@test.com",
            "password": "TestPass123!",
            "full_name": "Scoped Client",
            "role": "team_member",
            "feature_access": {"contacts": True},  # ONE module selected
            "send_invite": False,
        },
    )
    assert r.status_code == 201, r.text
    returned = r.json()["data"]["feature_access"]
    granted = sorted(f for f, on in returned.items() if on)

    created = (
        await db.execute(select(User).where(User.email == "scoped-client@test.com"))
    ).scalar_one()

    # The account should be able to reach contacts...
    ok = await client.get("/api/contacts", headers=auth_header(created))
    assert ok.status_code == 200, ok.text

    # ...and must NOT reach a module the admin never selected.
    blocked = await client.get("/api/cashbook/entries", headers=auth_header(created))
    assert blocked.status_code == 403, (
        f"Account reached /api/cashbook without it being selected. "
        f"Effective grants were: {granted}"
    )
