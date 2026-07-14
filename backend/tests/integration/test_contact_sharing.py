"""Manager visibility, explicit sharing, the file cascade, and offboarding.

Records are private to their owner. These are the three sanctioned ways a record
reaches anyone else:

    1. ADMIN sees everything.
    2. A MANAGER sees their DIRECT reports' records.
    3. A contact is EXPLICITLY shared — and its whole file goes with it.

Plus the offboarding path: an admin can hand a departing employee's book to
someone else, because created_by is otherwise immutable and their contacts would
be reachable only by an admin forever.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.auth.models import Role, User
from app.contacts.models import Contact, ContactAccess, SharePermission
from app.contacts.service import (
    list_contact_collaborators,
    share_contact,
    transfer_all_contacts,
    transfer_contact_ownership,
    unshare_contact,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from tests.conftest import auth_header, contact_owned_by


@pytest.fixture
def owner(team_member_user: User) -> User:
    return team_member_user


async def _contact_for(db, user: User, name: str = "Owned Co") -> Contact:
    contact = contact_owned_by(user, name)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


# ---------------------------------------------------------------------------
# 1. Owner privacy — the baseline
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_two_employees_cannot_see_each_others_contacts(
    client, db, owner: User, other_member_user: User
):
    """The reason the whole model exists: two people working the phones must not
    see each other's book."""
    mine = await _contact_for(db, owner, "Mine Ltd")

    resp = await client.get(
        f"/api/contacts/{mine.id}", headers=auth_header(other_member_user)
    )
    assert resp.status_code == 404

    resp = await client.get("/api/contacts", headers=auth_header(other_member_user))
    assert str(mine.id) not in [c["id"] for c in resp.json()["data"]]


# ---------------------------------------------------------------------------
# 2. Manager visibility
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_manager_sees_a_direct_reports_contact(
    client, db, manager_user: User, report_user: User
):
    theirs = await _contact_for(db, report_user, "Report Co")

    resp = await client.get(
        f"/api/contacts/{theirs.id}", headers=auth_header(manager_user)
    )
    assert resp.status_code == 200

    resp = await client.get("/api/contacts", headers=auth_header(manager_user))
    assert str(theirs.id) in [c["id"] for c in resp.json()["data"]]


@pytest.mark.critical
async def test_manager_does_not_see_a_non_reports_contact(
    client, db, manager_user: User, other_member_user: User
):
    """A manager sees their OWN reports, not the whole agency. Otherwise
    'manager' is just a second admin."""
    theirs = await _contact_for(db, other_member_user, "Not My Report Co")

    resp = await client.get(
        f"/api/contacts/{theirs.id}", headers=auth_header(manager_user)
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_visibility_does_not_flow_upward(
    client, db, manager_user: User, report_user: User
):
    """A report must not see their manager's contacts. Visibility is
    one-directional, down the reporting line."""
    boss_contact = await _contact_for(db, manager_user, "Boss Co")

    resp = await client.get(
        f"/api/contacts/{boss_contact.id}", headers=auth_header(report_user)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Explicit sharing
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_share_grants_read_then_unshare_revokes_it(
    client, db, owner: User, other_member_user: User
):
    contact = await _contact_for(db, owner, "Shared Co")
    headers = auth_header(other_member_user)

    assert (
        await client.get(f"/api/contacts/{contact.id}", headers=headers)
    ).status_code == 404

    resp = await client.post(
        f"/api/contacts/{contact.id}/share",
        json={"user_id": str(other_member_user.id), "permission": "view"},
        headers=auth_header(owner),
    )
    assert resp.status_code == 201, resp.text

    assert (
        await client.get(f"/api/contacts/{contact.id}", headers=headers)
    ).status_code == 200

    resp = await client.delete(
        f"/api/contacts/{contact.id}/share/{other_member_user.id}",
        headers=auth_header(owner),
    )
    assert resp.status_code == 200

    assert (
        await client.get(f"/api/contacts/{contact.id}", headers=headers)
    ).status_code == 404, "revoking access must actually revoke it"


@pytest.mark.critical
async def test_view_only_share_cannot_edit(
    client, db, owner: User, other_member_user: User
):
    """The permission has to mean something."""
    contact = await _contact_for(db, owner, "ReadOnly Co")
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.VIEW)

    resp = await client.put(
        f"/api/contacts/{contact.id}",
        json={"company_name": "Hijacked"},
        headers=auth_header(other_member_user),
    )
    assert resp.status_code == 403, "view-only means view-only"

    # 403 not 404 here is deliberate: they can already SEE it, so refusing with
    # 403 leaks nothing they weren't shown.


@pytest.mark.critical
async def test_edit_share_can_edit(client, db, owner: User, other_member_user: User):
    contact = await _contact_for(db, owner, "Editable Co")
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.EDIT)

    resp = await client.put(
        f"/api/contacts/{contact.id}",
        json={"company_name": "Worked The File"},
        headers=auth_header(other_member_user),
    )
    assert resp.status_code == 200


@pytest.mark.critical
async def test_resharing_is_an_upsert_not_a_duplicate(
    db, owner: User, other_member_user: User
):
    contact = await _contact_for(db, owner, "Upsert Co")
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.VIEW)
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.EDIT)

    rows = (
        await db.execute(
            select(ContactAccess).where(ContactAccess.contact_id == contact.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].permission == SharePermission.EDIT


@pytest.mark.critical
async def test_you_cannot_reshare_what_was_shared_with_you(
    db, owner: User, other_member_user: User, viewer_user: User
):
    """Otherwise one grant leaks transitively across the whole team."""
    contact = await _contact_for(db, owner, "NoReshare Co")
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.EDIT)

    with pytest.raises(NotFoundError):
        await share_contact(
            db, contact.id, other_member_user, viewer_user.id, SharePermission.VIEW
        )


@pytest.mark.critical
async def test_a_contact_cannot_be_shared_with_a_portal_client(
    db, owner: User, client_user: User
):
    """A client's only surface is the portal. A CRM grant would walk them into
    the book."""
    contact = await _contact_for(db, owner, "NoClient Co")

    with pytest.raises(ForbiddenError):
        await share_contact(db, contact.id, owner, client_user.id, SharePermission.VIEW)


@pytest.mark.high
async def test_collaborators_are_listed(db, owner: User, other_member_user: User):
    contact = await _contact_for(db, owner, "Collab Co")
    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.EDIT)

    rows = await list_contact_collaborators(db, contact.id, owner)
    assert len(rows) == 1
    assert rows[0]["user_id"] == other_member_user.id
    assert rows[0]["permission"] == "edit"


# ---------------------------------------------------------------------------
# 4. The cascade — sharing a contact hands over its whole file
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_sharing_a_contact_cascades_to_its_invoices(
    client, db, owner: User, other_member_user: User
):
    """A contact you can't see the file of is just a name and a phone number."""
    from app.invoicing.models import Invoice, InvoiceStatus

    contact = await _contact_for(db, owner, "Cascade Co")
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number="INV-CASCADE-1",
        contact_id=contact.id,
        issue_date=date.today(),
        due_date=date.today(),
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        currency="USD",
        status=InvoiceStatus.SENT,
        created_by=owner.id,
    )
    db.add(invoice)
    await db.commit()

    headers = auth_header(other_member_user)

    # Before the share: invisible.
    assert (
        await client.get(f"/api/invoices/{invoice.id}", headers=headers)
    ).status_code == 404

    await share_contact(db, contact.id, owner, other_member_user.id, SharePermission.VIEW)

    # After: the file comes with it.
    resp = await client.get(f"/api/invoices/{invoice.id}", headers=headers)
    assert resp.status_code == 200, "sharing the contact must hand over its file"


@pytest.mark.critical
async def test_cascade_does_not_leak_unrelated_records(
    client, db, owner: User, other_member_user: User
):
    """Sharing ONE contact must not hand over the owner's other contacts' files."""
    from app.invoicing.models import Invoice, InvoiceStatus

    shared = await _contact_for(db, owner, "Shared Co")
    private = await _contact_for(db, owner, "Private Co")

    secret = Invoice(
        id=uuid.uuid4(),
        invoice_number="INV-SECRET-1",
        contact_id=private.id,
        issue_date=date.today(),
        due_date=date.today(),
        subtotal=Decimal("999.00"),
        total=Decimal("999.00"),
        currency="USD",
        status=InvoiceStatus.SENT,
        created_by=owner.id,
    )
    db.add(secret)
    await db.commit()

    await share_contact(db, shared.id, owner, other_member_user.id, SharePermission.EDIT)

    resp = await client.get(
        f"/api/invoices/{secret.id}", headers=auth_header(other_member_user)
    )
    assert resp.status_code == 404, (
        "a share is a share of ONE contact's file, not of the owner's whole book"
    )


# ---------------------------------------------------------------------------
# 5. Offboarding — transfer of ownership
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_admin_can_transfer_a_contact_and_its_file(
    client, db, admin_user: User, owner: User, other_member_user: User
):
    contact = await _contact_for(db, owner, "Handover Co")

    transferred = await transfer_contact_ownership(
        db, contact.id, admin_user, other_member_user.id
    )
    assert transferred.created_by == other_member_user.id

    # New owner sees it outright...
    assert (
        await client.get(
            f"/api/contacts/{contact.id}", headers=auth_header(other_member_user)
        )
    ).status_code == 200

    # ...and the previous owner no longer does.
    assert (
        await client.get(f"/api/contacts/{contact.id}", headers=auth_header(owner))
    ).status_code == 404


@pytest.mark.critical
async def test_only_an_admin_can_transfer_ownership(
    db, owner: User, other_member_user: User
):
    contact = await _contact_for(db, owner, "NoSteal Co")

    with pytest.raises(ForbiddenError):
        await transfer_contact_ownership(db, contact.id, owner, other_member_user.id)


@pytest.mark.critical
async def test_transferring_a_whole_book_when_someone_leaves(
    db, admin_user: User, owner: User, other_member_user: User
):
    """The offboarding path. created_by is immutable, so without this a departing
    employee's entire book would be reachable only by an admin, forever."""
    for i in range(3):
        await _contact_for(db, owner, f"Departing Co {i}")

    moved = await transfer_all_contacts(db, admin_user, owner.id, other_member_user.id)
    assert moved == 3

    remaining = (
        await db.execute(select(Contact).where(Contact.created_by == owner.id))
    ).scalars().all()
    assert remaining == []

    now_theirs = (
        await db.execute(
            select(Contact).where(Contact.created_by == other_member_user.id)
        )
    ).scalars().all()
    assert len(now_theirs) == 3
