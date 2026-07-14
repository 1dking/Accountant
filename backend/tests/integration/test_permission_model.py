"""The permission model, pinned.

Decision: staff share one book of business; the ROUTE layer (require_role)
decides what each role may DO with it. Ownership is no longer a second gate on
shared business records — it made the VIEWER role useless by construction (a
viewer creates nothing, so it could see nothing) and stopped two team members
from seeing each other's contacts, which makes a shared CRM pointless.

Two things this must NOT have done, and both are asserted here:
  1. CLIENT is not staff. A portal user must not be able to walk the book of
     business just by holding a session.
  2. Private resources stay owner-scoped — Drive documents, meetings, and above
     all SMTP configs, which hold encrypted credentials.
"""
import uuid

import pytest
from sqlalchemy import select

from app.auth.models import Role, User
from app.core.authorization import (
    apply_shared_filter,
    authorize_owner,
    authorize_shared,
    is_staff,
)
from app.core.exceptions import NotFoundError
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# The model itself
# ---------------------------------------------------------------------------


@pytest.mark.critical
def test_staff_roles_are_exactly_the_internal_ones(
    admin_user: User, team_member_user: User, viewer_user: User, client_user: User
):
    assert is_staff(admin_user)
    assert is_staff(team_member_user)
    assert is_staff(viewer_user)
    assert not is_staff(client_user), "a CLIENT is an outsider, not staff"


@pytest.mark.critical
def test_staff_may_reach_a_record_they_did_not_create(
    viewer_user: User, team_member_user: User, admin_user: User
):
    """The whole point: a viewer creates nothing, so under the old rule it could
    see nothing."""
    someone_elses = admin_user.id
    authorize_shared(someone_elses, viewer_user, "Contact")
    authorize_shared(someone_elses, team_member_user, "Contact")


@pytest.mark.critical
def test_a_client_still_must_own_the_record(client_user: User, admin_user: User):
    """If this ever passes for a record they don't own, a portal user can walk
    the entire book of business."""
    with pytest.raises(NotFoundError):
        authorize_shared(admin_user.id, client_user, "Contact")

    # ...and may still reach their own.
    authorize_shared(client_user.id, client_user, "Contact")


@pytest.mark.critical
def test_private_resources_are_still_owner_only(
    viewer_user: User, team_member_user: User, admin_user: User
):
    """authorize_owner is what guards SMTP configs (encrypted credentials),
    Drive documents and meetings. Loosening the shared path must not have
    loosened this one."""
    for staff in (viewer_user, team_member_user):
        with pytest.raises(NotFoundError):
            authorize_owner(admin_user.id, staff, "SmtpConfig")

    # Admin still bypasses; owner still reaches their own.
    authorize_owner(viewer_user.id, admin_user, "SmtpConfig")
    authorize_owner(viewer_user.id, viewer_user, "SmtpConfig")


# ---------------------------------------------------------------------------
# End to end through the API
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_viewer_reads_a_contact_created_by_someone_else(
    client, viewer_user: User, sample_contact
):
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(viewer_user)
    )
    assert resp.status_code == 200


@pytest.mark.critical
async def test_viewer_still_cannot_create_a_contact(client, viewer_user: User):
    """Read access must not have leaked into write access — that's the route
    layer's job and it must still say no."""
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
    """Delete stayed admin-only."""
    resp = await client.delete(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(team_member_user)
    )
    assert resp.status_code == 403


@pytest.mark.critical
async def test_client_cannot_see_the_contact_book(
    client, client_user: User, sample_contact
):
    """The contacts list/get routes are gated only by get_current_user — ANY
    authenticated role reaches them, CLIENT included (create/update/delete are
    the ones behind require_role).

    So the service-layer filter is the ONLY thing standing between a portal user
    and the entire contact book. This is precisely why CLIENT must not be in
    STAFF_ROLES: apply_shared_filter falls back to the owner filter for
    non-staff, and a client creates nothing, so it sees nothing.

    The list returns 200 with an EMPTY payload, not 403 — asserting on the
    status code alone would miss a leak entirely. Assert on the DATA.
    """
    resp = await client.get("/api/contacts", headers=auth_header(client_user))
    assert resp.status_code == 200
    assert resp.json()["data"] == [], (
        "a portal user must not be able to list the contact book"
    )

    # And a direct hit on someone else's contact is not found for them.
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}", headers=auth_header(client_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_client_cannot_read_payments_of_a_contact_they_do_not_own(
    client, client_user: User, sample_contact
):
    """/contacts/{id}/payments is gated by get_current_user, not require_role —
    so a CLIENT reaches the service layer. authorize_shared is the only thing
    standing between them and someone else's payment history."""
    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/payments",
        headers=auth_header(client_user),
    )
    assert resp.status_code in (403, 404), (
        "a portal user must not read another contact's payments"
    )


# The soft-delete fix (get_entry now hides deleted rows, so a deleted entry
# stops returning 200) is already covered end-to-end by
# tests/api/test_cashbook.py::test_crud_entries — which is the test that was
# failing on exactly that assertion. Not duplicated here.
