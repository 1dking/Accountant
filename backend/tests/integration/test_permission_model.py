"""The permission model, pinned.

Records are PRIVATE TO THEIR OWNER. Each employee has their own section: two
people working the phones must not see each other's contacts. Only ADMIN (the
agency owner) sees across everyone. A colleague gets a record only when it is
EXPLICITLY shared with them.

This file previously asserted the opposite — that any staff role could read any
business record. That was written from a test suite which encoded a
shared-workspace product the business does not want. If a future change makes
these tests fail because "the viewer role can't see anything", that is the
intended behaviour, not a bug to fix by loosening the check.
"""
import uuid

import pytest

from app.auth.models import Role, User
from app.core.authorization import (
    apply_ownership_filter,
    authorize_owner,
    is_admin,
)
from app.core.exceptions import NotFoundError
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# The primitive
# ---------------------------------------------------------------------------


@pytest.mark.critical
def test_owner_reaches_their_own_record(team_member_user: User):
    authorize_owner(team_member_user.id, team_member_user, "Contact")


@pytest.mark.critical
def test_a_colleague_cannot_reach_a_record_they_do_not_own(
    team_member_user: User, viewer_user: User, admin_user: User
):
    """The core rule. Two salespeople must not see each other's book."""
    for other in (team_member_user, viewer_user):
        with pytest.raises(NotFoundError):
            authorize_owner(admin_user.id, other, "Contact")


@pytest.mark.critical
def test_admin_sees_across_everyone(admin_user: User, team_member_user: User):
    """The agency owner is the one role that sees into every section."""
    assert is_admin(admin_user)
    authorize_owner(team_member_user.id, admin_user, "Contact")


@pytest.mark.critical
def test_not_found_not_forbidden(team_member_user: User, admin_user: User):
    """404, never 403 — a 403 would confirm the record exists, which leaks the
    shape of a colleague's book to anyone probing ids."""
    with pytest.raises(NotFoundError):
        authorize_owner(admin_user.id, team_member_user, "Contact")


# ---------------------------------------------------------------------------
# End to end through the API
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_team_member_cannot_read_another_users_contact(
    client, team_member_user: User, sample_contact
):
    """sample_contact belongs to admin_user."""
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(team_member_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_viewer_cannot_read_another_users_contact(
    client, viewer_user: User, sample_contact
):
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(viewer_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_a_colleagues_contacts_are_absent_from_my_list(
    client, team_member_user: User, sample_contact
):
    """Assert on the DATA, not the status. The list returns 200 with an empty
    payload — a status-only assertion would sail straight past a leak."""
    resp = await client.get("/api/contacts", headers=auth_header(team_member_user))
    assert resp.status_code == 200

    ids = [c["id"] for c in resp.json()["data"]]
    assert str(sample_contact.id) not in ids, (
        "a colleague's contact must not appear in my list"
    )


@pytest.mark.critical
async def test_admin_does_see_the_contact_in_their_list(
    client, admin_user: User, sample_contact
):
    resp = await client.get("/api/contacts", headers=auth_header(admin_user))
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["data"]]
    assert str(sample_contact.id) in ids


@pytest.mark.critical
async def test_client_cannot_see_the_contact_book(
    client, client_user: User, sample_contact
):
    """The contacts list/get routes are gated by get_current_user, NOT
    require_role — so a portal user does reach the service layer. The ownership
    filter is the only thing between them and the whole book."""
    resp = await client.get("/api/contacts", headers=auth_header(client_user))
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(client_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_viewer_still_cannot_create_a_contact(client, viewer_user: User):
    """Ownership governs WHICH records you see; require_role governs what you may
    DO. Those stay independent."""
    resp = await client.post(
        "/api/contacts",
        json={"type": "client", "company_name": "Nope Inc"},
        headers={**auth_header(viewer_user), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 403


@pytest.mark.critical
async def test_team_member_still_cannot_delete_a_contact(
    client, team_member_user: User, sample_contact
):
    """Delete is admin-only, and the contact isn't theirs anyway."""
    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(team_member_user)
    )
    assert resp.status_code in (403, 404)
