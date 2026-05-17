"""AI-generated contact brief.

Pulls contact info + recent memories + recent message events and asks
Claude Haiku to summarize the relationship in 2-3 sentences addressed
to the user. Cache TTL 1hr; cache invalidated on new memory/SMS/voicemail
via invalidate_brief_cache helper.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.communication.models import CallLog, SmsMessage
from app.config import Settings
from app.contacts.models import Contact, ContactMemory

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 400
CACHE_TTL = timedelta(hours=1)

SYSTEM_PROMPT = """You generate a 2-3 sentence brief on a contact, addressed \
to the platform user in second person ("They mentioned…", "Last time you \
spoke…"). Be specific, not generic. Use the most recent commitment, the \
clearest thing they care about, and one concrete thing to bring up next \
time. If the available context is thin, say so plainly — don't invent. \
Output the brief as a single paragraph, no headings, no markdown."""


def _is_fresh(generated_at: datetime | None) -> bool:
    if generated_at is None:
        return False
    if generated_at.tzinfo is None:
        # SQLite returns naive datetimes; assume UTC
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - generated_at) < CACHE_TTL


async def _gather_context(
    db: AsyncSession, contact_id: uuid.UUID
) -> tuple[Contact | None, str]:
    """Assemble the input text for the brief from contact fields +
    recent memories + recent message events."""
    contact_row = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_row.scalar_one_or_none()
    if contact is None:
        return None, ""

    parts: list[str] = []
    parts.append(f"Contact: {contact.contact_name or '(no name)'}")
    if contact.company_name:
        parts.append(f"Company: {contact.company_name}")
    parts.append(f"Type: {contact.type.value if contact.type else 'unknown'}")
    if contact.job_title:
        parts.append(f"Role: {contact.job_title}")
    if contact.email:
        parts.append(f"Email: {contact.email}")
    if contact.phone:
        parts.append(f"Phone: {contact.phone}")
    if contact.notes:
        parts.append(f"Notes: {contact.notes[:500]}")

    # Last 10 memory entries
    memory_rows = await db.execute(
        select(ContactMemory)
        .where(ContactMemory.contact_id == contact_id)
        .order_by(ContactMemory.created_at.desc())
        .limit(10)
    )
    memories = list(memory_rows.scalars().all())
    if memories:
        parts.append("\nRecent memories (newest first):")
        for m in memories:
            chunks = []
            if m.summary:
                chunks.append(f"summary: {m.summary}")
            if m.commitments and m.commitments.lower() != "none":
                chunks.append(f"commitments: {m.commitments}")
            if m.cares_about and m.cares_about.lower() != "unclear":
                chunks.append(f"cares about: {m.cares_about}")
            if m.talking_points and m.talking_points.lower() != "unclear":
                chunks.append(f"next time: {m.talking_points}")
            if chunks:
                parts.append(f"- [{m.source_type}] " + " | ".join(chunks))

    # Last 5 SMS bodies (any direction)
    sms_rows = await db.execute(
        select(SmsMessage)
        .where(SmsMessage.contact_id == contact_id)
        .order_by(SmsMessage.created_at.desc())
        .limit(5)
    )
    sms_list = list(sms_rows.scalars().all())
    if sms_list:
        parts.append("\nRecent SMS (newest first):")
        for s in sms_list:
            tag = "they" if s.direction == "inbound" else "you"
            parts.append(f"- [{tag}] {(s.body or '')[:200]}")

    # Last 3 voicemails with transcripts
    vm_rows = await db.execute(
        select(CallLog)
        .where(
            CallLog.contact_id == contact_id,
            CallLog.kind == "voicemail",
            CallLog.voicemail_transcript.is_not(None),
        )
        .order_by(CallLog.created_at.desc())
        .limit(3)
    )
    vms = list(vm_rows.scalars().all())
    if vms:
        parts.append("\nRecent voicemails (newest first):")
        for v in vms:
            parts.append(f"- {(v.voicemail_transcript or '')[:300]}")

    return contact, "\n".join(parts)


async def generate_brief(db: AsyncSession, contact_id: uuid.UUID) -> str | None:
    """Generate (or regenerate) the AI brief. Returns the brief text on
    success, None on Claude failure (caller decides fallback)."""
    settings = Settings()
    if not settings.anthropic_api_key:
        return None

    contact, ctx = await _gather_context(db, contact_id)
    if contact is None:
        return None

    if not ctx.strip():
        return None

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": ctx}],
            timeout=15.0,
        )
        brief = "".join(
            b.text for b in response.content
            if getattr(b, "type", "") == "text"
        ).strip()
        if not brief:
            return None
    except Exception as e:
        logger.warning(
            "ai_brief.generation_failed contact_id=%s error=%s",
            contact_id, str(e)[:200],
        )
        return None

    contact.ai_brief = brief
    contact.ai_brief_generated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("ai_brief.generated contact_id=%s chars=%d", contact_id, len(brief))
    return brief


async def invalidate_brief_cache(
    db: AsyncSession, contact_id: uuid.UUID | None
) -> None:
    """Clear the cached brief so the next /brief call regenerates.

    Called from memory_writer + SMS persistence + voicemail handler.
    Safe to call with None contact_id (no-op)."""
    if contact_id is None:
        return
    contact_row = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_row.scalar_one_or_none()
    if contact is not None and contact.ai_brief_generated_at is not None:
        contact.ai_brief_generated_at = None
        await db.commit()
