"""Business logic for the client portal."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.contacts.models import ClientPortalAccount, Contact, FileShare
from app.core.exceptions import NotFoundError


async def get_portal_dashboard(db: AsyncSession, user: User) -> dict:
    """Get dashboard data for a portal client."""
    portal = await _get_portal_account(db, user.id)
    contact = await _get_contact(db, portal.contact_id)

    from app.invoicing.models import Invoice, InvoiceStatus

    # Pending invoices
    inv_q = select(func.count(), func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.contact_id == contact.id,
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
    )
    inv_row = (await db.execute(inv_q)).one()
    pending_invoices = inv_row[0] or 0
    total_outstanding = float(inv_row[1] or 0)

    # Pending proposals
    from app.proposals.models import Proposal

    prop_count = (
        await db.execute(
            select(func.count(Proposal.id)).where(
                Proposal.contact_id == contact.id,
                Proposal.status == "sent",
            )
        )
    ).scalar() or 0

    # Shared files
    file_count = (
        await db.execute(
            select(func.count(FileShare.id)).where(
                FileShare.contact_id == contact.id
            )
        )
    ).scalar() or 0

    # Upcoming meetings
    from app.meetings.models import Meeting, MeetingStatus

    meeting_count = (
        await db.execute(
            select(func.count(Meeting.id)).where(
                Meeting.contact_id == contact.id,
                Meeting.status == MeetingStatus.SCHEDULED,
                Meeting.scheduled_start >= datetime.now(timezone.utc),
            )
        )
    ).scalar() or 0

    return {
        "contact_name": contact.contact_name,
        "company_name": contact.company_name,
        "pending_invoices": pending_invoices,
        "total_outstanding": total_outstanding,
        "pending_proposals": prop_count,
        "shared_files": file_count,
        "upcoming_meetings": meeting_count,
    }


async def get_portal_invoices(db: AsyncSession, user: User) -> list[dict]:
    portal = await _get_portal_account(db, user.id)
    from app.invoicing.models import Invoice

    q = (
        select(Invoice)
        .where(Invoice.contact_id == portal.contact_id)
        .order_by(Invoice.issue_date.desc())
    )
    result = await db.execute(q)
    invoices = result.scalars().all()
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "issue_date": str(inv.issue_date),
            "due_date": str(inv.due_date),
            "total": float(inv.total),
            "currency": inv.currency,
            "status": inv.status.value if hasattr(inv.status, "value") else inv.status,
            "payment_url": None,
        }
        for inv in invoices
    ]


async def get_portal_proposals(db: AsyncSession, user: User) -> list[dict]:
    portal = await _get_portal_account(db, user.id)
    from app.proposals.models import Proposal

    q = (
        select(Proposal)
        .where(Proposal.contact_id == portal.contact_id)
        .order_by(Proposal.created_at.desc())
    )
    result = await db.execute(q)
    proposals = result.scalars().all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "status": p.status,
            "total": float(p.total) if p.total else None,
            "created_at": p.created_at,
            "signing_token": p.signing_token if hasattr(p, "signing_token") else None,
        }
        for p in proposals
    ]


async def get_portal_files(db: AsyncSession, user: User) -> list[dict]:
    from app.contacts.service import list_shared_files_for_portal

    portal = await _get_portal_account(db, user.id)
    return await list_shared_files_for_portal(db, portal.contact_id)


async def get_portal_meetings(db: AsyncSession, user: User) -> list[dict]:
    portal = await _get_portal_account(db, user.id)
    from app.meetings.models import Meeting

    q = (
        select(Meeting)
        .where(Meeting.contact_id == portal.contact_id)
        .order_by(Meeting.scheduled_start.desc())
    )
    result = await db.execute(q)
    meetings = result.scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "scheduled_start": m.scheduled_start,
            "scheduled_end": m.scheduled_end,
            "status": m.status.value if hasattr(m.status, "value") else m.status,
        }
        for m in meetings
    ]


async def _get_portal_account(
    db: AsyncSession, user_id: uuid.UUID
) -> ClientPortalAccount:
    result = await db.execute(
        select(ClientPortalAccount).where(
            ClientPortalAccount.user_id == user_id,
            ClientPortalAccount.is_active == True,
        )
    )
    portal = result.scalar_one_or_none()
    if portal is None:
        raise NotFoundError("PortalAccount", str(user_id))
    return portal


async def _get_contact(db: AsyncSession, contact_id: uuid.UUID) -> Contact:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise NotFoundError("Contact", str(contact_id))
    return contact
