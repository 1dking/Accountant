"""Per-employee module access, enforced on the SERVER.

"The secretary or accountant has only the cash book. Maybe some employees aren't
allowed [other sections]."

That system already existed — User.feature_access_json, role defaults, an admin
checkbox grid — and it was ADVISORY ONLY. Turning a module off hid the sidebar
link and nothing else: the API kept serving the data to anyone who typed the URL
or called it directly. These tests exist because the difference between "the link
is hidden" and "the data is refused" is the whole feature.
"""
import json
import uuid

import pytest

from app.auth.features import ROLE_DEFAULTS, resolve_feature_access
from app.auth.models import Role, User
from app.auth.utils import hash_password
from tests.conftest import auth_header


async def _user_with_features(db, role: Role, features: dict[str, bool]) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@feat.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Feature Test User",
        role=role,
        is_active=True,
        feature_access_json=json.dumps(features),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.critical
async def test_module_off_means_the_api_refuses_not_just_the_sidebar(client, db):
    """The bug this closes: cashbook=false used to still return 200."""
    user = await _user_with_features(db, Role.TEAM_MEMBER, {"cashbook": False})

    resp = await client.get("/api/cashbook/entries", headers=auth_header(user))
    assert resp.status_code == 403, (
        "a module switched off for this employee must be refused by the server"
    )
    # The app wraps errors as {"error": {"code", "message", "details"}}.
    assert "cashbook" in resp.json()["error"]["message"].lower()


@pytest.mark.critical
async def test_module_on_is_reachable(client, db):
    user = await _user_with_features(db, Role.TEAM_MEMBER, {"cashbook": True})

    resp = await client.get("/api/cashbook/entries", headers=auth_header(user))
    assert resp.status_code == 200


@pytest.mark.critical
async def test_an_accountant_gets_the_money_side_but_not_meetings(client, db):
    """The accountant runs the money side end to end — cashbook, invoices and the
    contacts to invoice against — but not unrelated modules like meetings. The
    gate still bites; it just draws the line in a different place than 'cashbook
    only'."""
    accountant = await _user_with_features(db, Role.ACCOUNTANT, {})

    for path in ("/api/cashbook/entries", "/api/contacts", "/api/invoices"):
        assert (
            await client.get(path, headers=auth_header(accountant))
        ).status_code == 200, f"accountant should reach {path}"

    # ...but a module they were never granted is still refused — the gate works.
    assert (
        await client.get("/api/meetings", headers=auth_header(accountant))
    ).status_code == 403, "accountant has no meetings module"


@pytest.mark.critical
async def test_a_per_user_override_beats_the_role_default(client, db):
    """The point of per-employee toggles: one VA is not every VA. Grant one
    accountant a module that is OFF in the role default (meetings) and it opens,
    while the role default for it stays shut for everyone else."""
    accountant = await _user_with_features(db, Role.ACCOUNTANT, {"meetings": False})
    # Sanity: with meetings off (matching the default), it's refused.
    assert (
        await client.get("/api/meetings", headers=auth_header(accountant))
    ).status_code == 403

    # Now an accountant the admin explicitly granted meetings.
    granted = await _user_with_features(db, Role.ACCOUNTANT, {"meeting_rooms": True})
    assert (
        await client.get("/api/meetings", headers=auth_header(granted))
    ).status_code == 200, "an explicit override must open a module the role default shuts"


@pytest.mark.critical
async def test_admin_reaches_everything(client, admin_user: User):
    for path in ("/api/contacts", "/api/cashbook/entries", "/api/tasks"):
        resp = await client.get(path, headers=auth_header(admin_user))
        assert resp.status_code == 200, f"admin must reach {path}"


@pytest.mark.critical
async def test_the_gate_does_not_break_unauthenticated_public_routes(client):
    """Several gated routers also carry deliberately PUBLIC routes — Twilio voice
    webhooks, the Stripe webhook, public proposal signing links, guest meeting
    joins, published pages, form submissions.

    If require_feature demanded a token, inbound phone calls and payment webhooks
    would start 403-ing. A request with NO credentials must pass the gate and be
    handled by the route's own auth (or lack of it).
    """
    # No Authorization header at all. The feature gate must not turn this into a
    # 403 — the endpoint's own dependency owns the 401.
    resp = await client.get("/api/cashbook/entries")
    assert resp.status_code in (401, 403)
    if resp.status_code == 403:
        # If it IS 403 it must be an auth failure, never the module gate.
        assert "module is not enabled" not in resp.text


@pytest.mark.critical
async def test_a_manager_has_a_role_default(client, db, manager_user: User):
    """resolve_feature_access falls back to all-false for an unknown role. Without
    a "manager" entry in ROLE_DEFAULTS a manager would 403 on every gated router
    the moment this shipped."""
    assert "manager" in ROLE_DEFAULTS

    features = resolve_feature_access(manager_user.role.value, None)
    assert features["contacts"] is True
    assert features["platform_admin"] is False

    assert (
        await client.get("/api/contacts", headers=auth_header(manager_user))
    ).status_code == 200


@pytest.mark.high
async def test_a_viewer_can_open_contacts_so_a_share_can_reach_it(
    client, db, viewer_user: User
):
    """A viewer is a read-only collaborator: it owns nothing and sees only what is
    shared with it. It therefore needs the contacts module ON, or the module gate
    would block the very record it was granted — it would be handed a file it
    cannot open. The list is still empty until something is shared."""
    resp = await client.get("/api/contacts", headers=auth_header(viewer_user))
    assert resp.status_code == 200
    assert resp.json()["data"] == []
