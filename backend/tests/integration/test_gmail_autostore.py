"""Emailed attachments auto-file as Documents.

The scheduled Gmail scan downloads each invoice/receipt attachment to storage but
used to create no queryable record — the file only became a Document when a human
opened the scan result and clicked import. If nobody clicked, the invoice sat on
disk, invisible in Drive. `_auto_store_attachments` closes that: every downloaded
attachment becomes a Document owned by the scanned account's user, deduped by
content hash, with no AI and no expense (Expense.amount is NOT NULL — that stays a
one-click review step).

These test the helper directly: the download itself is Gmail I/O, but by the time
the helper runs the bytes are already saved and hashed, which is the seam we own.
"""
import hashlib
import uuid

import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.documents.models import Document, DocumentStatus, DocumentType
from app.integrations.gmail.models import GmailAccount, GmailScanResult
from app.integrations.gmail.service import _auto_store_attachments


async def _account(db, user: User) -> GmailAccount:
    acct = GmailAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        email="scanned@gmail.com",
        encrypted_access_token="x",
        encrypted_refresh_token="x",
        scopes="",
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


async def _scan_result(db, acct: GmailAccount, message_id: str) -> GmailScanResult:
    row = GmailScanResult(
        id=uuid.uuid4(),
        gmail_account_id=acct.id,
        message_id=message_id,
        subject="Your invoice from Acme",
        has_attachments=True,
        is_processed=False,
    )
    db.add(row)
    await db.flush()
    return row


def _att(name: str, content: bytes, storage_path: str | None = None) -> dict:
    return {
        "filename": name,
        "storage_path": storage_path or f"r2/{uuid.uuid4().hex}",
        "size": len(content),
        "file_hash": hashlib.sha256(content).hexdigest(),
    }


@pytest.mark.critical
async def test_attachment_becomes_a_document(db, admin_user: User):
    acct = await _account(db, admin_user)
    row = await _scan_result(db, acct, "msg-1")

    content = b"%PDF-1.4 a real invoice " + b"x" * 4000
    att = _att("invoice_123.pdf", content)

    await _auto_store_attachments(db, acct, row, [att], "Your invoice from Acme")
    await db.commit()

    docs = (
        await db.execute(select(Document).where(Document.uploaded_by == admin_user.id))
    ).scalars().all()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.original_filename == "invoice_123.pdf"
    assert doc.file_hash == att["file_hash"]
    assert doc.storage_path == att["storage_path"]
    assert doc.document_type == DocumentType.INVOICE  # inferred from the name
    assert doc.status == DocumentStatus.PENDING_REVIEW
    assert doc.extracted_metadata["source"] == "gmail"

    # The scan result is marked handled and linked to the document.
    assert row.is_processed is True
    assert row.matched_document_id == doc.id


@pytest.mark.critical
async def test_no_expense_is_created(db, admin_user: User):
    """Deliberate: auto-store files the document, it does NOT book an expense."""
    from app.accounting.models import Expense

    acct = await _account(db, admin_user)
    row = await _scan_result(db, acct, "msg-2")

    await _auto_store_attachments(
        db, acct, row, [_att("receipt.pdf", b"receipt bytes " + b"y" * 3000)], "Receipt"
    )
    await db.commit()

    n = (await db.execute(select(func.count(Expense.id)))).scalar()
    assert n == 0


@pytest.mark.critical
async def test_the_same_file_is_not_filed_twice(db, admin_user: User):
    """Dedup by (file_hash, uploaded_by): a re-scan or a duplicate email must not
    create a second Document."""
    acct = await _account(db, admin_user)
    content = b"same invoice every time " + b"z" * 5000
    att = _att("invoice.pdf", content)

    row1 = await _scan_result(db, acct, "msg-3")
    await _auto_store_attachments(db, acct, row1, [att], "Invoice")
    await db.commit()

    # Second scan, same bytes (different storage_path, as a fresh download would be).
    row2 = await _scan_result(db, acct, "msg-4")
    att2 = _att("invoice.pdf", content)
    await _auto_store_attachments(db, acct, row2, [att2], "Invoice")
    await db.commit()

    n = (
        await db.execute(
            select(func.count(Document.id)).where(Document.uploaded_by == admin_user.id)
        )
    ).scalar()
    assert n == 1, "the same file must not be filed twice"
    # ...but the second scan result still gets linked to the existing document.
    assert row2.is_processed is True
    assert row2.matched_document_id is not None


@pytest.mark.high
async def test_tiny_and_non_document_attachments_are_skipped(db, admin_user: User):
    """A tracking pixel / signature logo / calendar invite shouldn't clutter Drive."""
    acct = await _account(db, admin_user)
    row = await _scan_result(db, acct, "msg-5")

    atts = [
        _att("pixel.png", b"tiny"),                    # under the size floor
        _att("event.ics", b"BEGIN:VCALENDAR" + b"a" * 4000),  # not a stored type
    ]
    await _auto_store_attachments(db, acct, row, atts, "Meeting")
    await db.commit()

    n = (
        await db.execute(
            select(func.count(Document.id)).where(Document.uploaded_by == admin_user.id)
        )
    ).scalar()
    assert n == 0
    # Nothing storable → the result stays in the manual queue.
    assert row.is_processed is False


@pytest.mark.high
async def test_documents_are_owned_by_the_scanned_account_user(
    db, admin_user: User, team_member_user: User
):
    """The document belongs to whoever's inbox was scanned — records are private,
    so it must not land under the wrong user."""
    acct = await _account(db, team_member_user)  # team member's mailbox
    row = await _scan_result(db, acct, "msg-6")

    await _auto_store_attachments(
        db, acct, row, [_att("invoice.pdf", b"team member invoice " + b"q" * 3000)], "Invoice"
    )
    await db.commit()

    doc = (
        await db.execute(select(Document).where(Document.file_hash != ""))
    ).scalars().first()
    assert doc.uploaded_by == team_member_user.id
    assert doc.uploaded_by != admin_user.id
