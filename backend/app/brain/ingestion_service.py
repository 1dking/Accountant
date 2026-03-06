"""Auto-ingestion hooks — event-driven embedding for new data."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.embedding_service import (
    embed_and_store,
    delete_embeddings_for_source,
    EmbeddingSourceType,
)

logger = logging.getLogger(__name__)


async def ingest_invoice(db: AsyncSession, user_id: uuid.UUID, invoice: object) -> None:
    """Embed an invoice when created/updated."""
    try:
        inv = invoice  # type: ignore
        content_parts = [
            f"Invoice #{inv.invoice_number}" if hasattr(inv, "invoice_number") else "",
            f"Client: {inv.client_name}" if hasattr(inv, "client_name") else "",
            f"Total: ${inv.total}" if hasattr(inv, "total") else "",
            f"Status: {inv.status}" if hasattr(inv, "status") else "",
            f"Due: {inv.due_date}" if hasattr(inv, "due_date") else "",
            f"Notes: {inv.notes}" if hasattr(inv, "notes") and inv.notes else "",
        ]
        content = " | ".join([p for p in content_parts if p])
        if not content:
            return

        source_id = str(inv.id)
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.INVOICE, source_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.INVOICE,
            source_id=source_id,
            contact_id=getattr(inv, "contact_id", None),
        )
    except Exception as e:
        logger.error(f"Failed to ingest invoice: {e}")


async def ingest_expense(db: AsyncSession, user_id: uuid.UUID, expense: object) -> None:
    """Embed an expense when created/updated."""
    try:
        exp = expense  # type: ignore
        content_parts = [
            f"Expense: {exp.description}" if hasattr(exp, "description") else "",
            f"Category: {exp.category}" if hasattr(exp, "category") else "",
            f"Amount: ${exp.amount}" if hasattr(exp, "amount") else "",
            f"Vendor: {exp.vendor}" if hasattr(exp, "vendor") and exp.vendor else "",
            f"Date: {exp.date}" if hasattr(exp, "date") else "",
        ]
        content = " | ".join([p for p in content_parts if p])
        if not content:
            return

        source_id = str(exp.id)
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.EXPENSE, source_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.EXPENSE,
            source_id=source_id,
        )
    except Exception as e:
        logger.error(f"Failed to ingest expense: {e}")


async def ingest_contact(db: AsyncSession, user_id: uuid.UUID, contact: object) -> None:
    """Embed a contact when created/updated."""
    try:
        c = contact  # type: ignore
        content_parts = [
            f"Contact: {c.name}" if hasattr(c, "name") else "",
            f"Company: {c.company}" if hasattr(c, "company") and c.company else "",
            f"Email: {c.email}" if hasattr(c, "email") and c.email else "",
            f"Phone: {c.phone}" if hasattr(c, "phone") and c.phone else "",
            f"Tags: {c.tags}" if hasattr(c, "tags") and c.tags else "",
            f"Notes: {c.notes}" if hasattr(c, "notes") and c.notes else "",
        ]
        content = " | ".join([p for p in content_parts if p])
        if not content:
            return

        source_id = str(c.id)
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.CONTACT, source_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.CONTACT,
            source_id=source_id,
        )
    except Exception as e:
        logger.error(f"Failed to ingest contact: {e}")


async def ingest_proposal(db: AsyncSession, user_id: uuid.UUID, proposal: object) -> None:
    """Embed a proposal when created/updated."""
    try:
        p = proposal  # type: ignore
        content_parts = [
            f"Proposal: {p.title}" if hasattr(p, "title") else "",
            f"Client: {p.client_name}" if hasattr(p, "client_name") else "",
            f"Total: ${p.total}" if hasattr(p, "total") else "",
            f"Status: {p.status}" if hasattr(p, "status") else "",
        ]
        # Include sections content if available
        if hasattr(p, "sections_json") and p.sections_json:
            try:
                import json
                sections = json.loads(p.sections_json)
                for sec in sections[:5]:  # Cap at 5 sections
                    if isinstance(sec, dict):
                        content_parts.append(sec.get("content", "")[:300])
            except Exception:
                pass

        content = " | ".join([p_item for p_item in content_parts if p_item])
        if not content:
            return

        source_id = str(p.id)
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.PROPOSAL, source_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.PROPOSAL,
            source_id=source_id,
            contact_id=getattr(p, "contact_id", None),
        )
    except Exception as e:
        logger.error(f"Failed to ingest proposal: {e}")


async def ingest_email(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject: str,
    body: str,
    sender: str = "",
    recipient: str = "",
    contact_id: uuid.UUID | None = None,
    source_id: str | None = None,
) -> None:
    """Embed an email message."""
    try:
        content = f"Email — Subject: {subject}\nFrom: {sender}\nTo: {recipient}\n\n{body[:2000]}"
        sid = source_id or str(uuid.uuid4())
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.EMAIL,
            source_id=sid,
            contact_id=contact_id,
        )
    except Exception as e:
        logger.error(f"Failed to ingest email: {e}")


async def ingest_sms(
    db: AsyncSession,
    user_id: uuid.UUID,
    body: str,
    phone_number: str = "",
    direction: str = "outbound",
    contact_id: uuid.UUID | None = None,
    source_id: str | None = None,
) -> None:
    """Embed an SMS message."""
    try:
        content = f"SMS ({direction}) — Phone: {phone_number}\n{body[:1000]}"
        sid = source_id or str(uuid.uuid4())
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.SMS,
            source_id=sid,
            contact_id=contact_id,
        )
    except Exception as e:
        logger.error(f"Failed to ingest SMS: {e}")


async def ingest_document(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    content: str,
    document_id: str,
) -> None:
    """Embed a document's content."""
    try:
        full_content = f"Document: {title}\n\n{content[:10000]}"
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.DOCUMENT, document_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=full_content,
            source_type=EmbeddingSourceType.DOCUMENT,
            source_id=document_id,
        )
    except Exception as e:
        logger.error(f"Failed to ingest document: {e}")


async def ingest_cashbook_entry(db: AsyncSession, user_id: uuid.UUID, entry: object) -> None:
    """Embed a cashbook entry."""
    try:
        e = entry  # type: ignore
        content_parts = [
            f"Cashbook: {e.description}" if hasattr(e, "description") else "",
            f"Amount: ${e.amount}" if hasattr(e, "amount") else "",
            f"Type: {e.entry_type}" if hasattr(e, "entry_type") else "",
            f"Category: {e.category}" if hasattr(e, "category") else "",
            f"Date: {e.date}" if hasattr(e, "date") else "",
        ]
        content = " | ".join([p for p in content_parts if p])
        if not content:
            return

        source_id = str(e.id)
        await delete_embeddings_for_source(db, user_id, EmbeddingSourceType.CASHBOOK, source_id)
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=content,
            source_type=EmbeddingSourceType.CASHBOOK,
            source_id=source_id,
        )
    except Exception as e_err:
        logger.error(f"Failed to ingest cashbook entry: {e_err}")
