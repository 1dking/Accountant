"""Email absorption pipeline — Session E.

Scans the user's connected Gmail account for messages from/to known
CRM contacts and absorbs each match into the contact's memory layer:
persists an absorbed_emails row, generates an AI summary via Claude
Haiku, writes a ContactMemory row, invalidates the AI brief cache.

Idempotency: `(user_id, gmail_message_id)` is the unique anchor. Re-
running the absorber over the same window is safe and produces zero
duplicates.

Contact-collision policy: a single email address may appear on more
than one Contact row (e.g., a person + their company). The matcher
picks the MOST RECENTLY CREATED contact deterministically — the same
contact is selected across runs because creation order is stable.

Privacy: only emails where the From or To header matches a CRM
contact's email are summarized. Unmatched emails are visited (we
need the headers) but their bodies are NEVER read or persisted.

Run lifecycle: the FastAPI endpoint creates an EmailAbsorptionRun
row in 'queued' status, then schedules `absorb_user_emails_task` via
BackgroundTasks. The worker flips status to 'running', updates
counters in-place as it progresses (frontend polls), and finally
sets 'complete' or 'failed' + finished_at. Failures never raise out
of the task — they're recorded in error_message.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.communication.models import AbsorbedEmail, EmailAbsorptionRun
from app.config import Settings
from app.contacts.models import Contact, ContactMemory
from app.integrations.gmail.models import GmailAccount
from app.integrations.gmail.service import (
    _extract_body_text,
    _extract_header,
    _get_gmail_service,
)

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS = 400
CLAUDE_TIMEOUT_SECONDS = 15.0
CLAUDE_BODY_MAX_CHARS = 4000
ANTHROPIC_CONCURRENCY = 50  # max simultaneous summarization calls

# Gmail search-query date cap: we never scan further back than this
# even if the run is configured with a larger lookback (defensive).
MAX_LOOKBACK_DAYS = 365

SUMMARY_SYSTEM_PROMPT = """\
You summarize a single email for a CRM memory note. Return JSON only \
(no markdown fences, no prose), matching this schema:

{
  "summary": "1-2 sentence overview of what was discussed. Focus on substance: commitments, key facts, next steps. Avoid restating the subject. Under 280 chars.",
  "commitments": "What was agreed or promised in this email (or 'none'). Under 200 chars.",
  "cares_about": "What the writer cares about / their concerns (or 'unclear'). Under 200 chars.",
  "talking_points": "1-3 things worth bringing up next time you talk to them. Under 200 chars."
}

Be specific, not generic. If the email is purely transactional/automated, \
say so plainly. If you can't extract a field, use 'unclear' or 'none'."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_email_address(header_value: str | None) -> str | None:
    """Pull the bare email out of a header like '"Sarah" <sarah@x.com>'.
    Returns lowercase or None."""
    if not header_value:
        return None
    _, addr = parseaddr(header_value)
    addr = (addr or "").strip().lower()
    return addr or None


def _extract_email_list(header_value: str | None) -> list[str]:
    """Parse a To/Cc header which may contain multiple comma-separated
    addresses. Returns lowercase emails."""
    if not header_value:
        return []
    # email.utils doesn't gracefully handle multiple addresses in one
    # parseaddr call; split on commas while respecting quoted names.
    parts = re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", header_value)
    out: list[str] = []
    for p in parts:
        addr = _extract_email_address(p)
        if addr:
            out.append(addr)
    return out


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def _summarize_email(
    *,
    subject: str | None,
    from_addr: str,
    to_addrs: list[str],
    direction: str,
    body_text: str,
    settings: Settings,
) -> dict:
    """Call Claude Haiku for the 4-field memory extraction.

    Returns {summary, commitments, cares_about, talking_points} as
    strings. On any error this function RE-RAISES — the caller decides
    whether to persist with summary=NULL or skip entirely. We don't
    swallow inside the helper so failures are visible at the call site.
    """
    if not settings.anthropic_api_key:
        raise ValueError("anthropic_api_key not configured")

    body_truncated = (body_text or "")[:CLAUDE_BODY_MAX_CHARS]
    direction_label = (
        "I sent this email" if direction == "outbound" else "I received this email"
    )

    user_msg = (
        f"Subject: {subject or '(no subject)'}\n"
        f"From: {from_addr}\n"
        f"To: {', '.join(to_addrs) if to_addrs else '(unknown)'}\n"
        f"Direction: {direction_label}\n\n"
        f"Body:\n{body_truncated}"
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        timeout=CLAUDE_TIMEOUT_SECONDS,
    )
    raw = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    cleaned = _strip_json_fences(raw)
    import json as _json
    parsed = _json.loads(cleaned)
    return {
        "summary": str(parsed.get("summary") or "")[:500],
        "commitments": str(parsed.get("commitments") or "")[:400],
        "cares_about": str(parsed.get("cares_about") or "")[:400],
        "talking_points": str(parsed.get("talking_points") or "")[:400],
    }


# ---------------------------------------------------------------------------
# Contact index
# ---------------------------------------------------------------------------


async def _build_contact_index(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[str, Contact]:
    """Return a {lower-cased email → Contact} index for absorption-
    eligible contacts (email IS NOT NULL AND email_absorption_enabled).

    Collision policy: if two contacts share an email, the most-recently-
    created one wins. The earlier rows are silently skipped — they
    can still be matched manually in the future but the absorber
    treats them as overshadowed by the newer row. Documented in module
    docstring; deterministic across runs.
    """
    rows = await db.execute(
        select(Contact)
        .where(
            Contact.email.is_not(None),
            Contact.email_absorption_enabled.is_(True),
            Contact.is_active.is_(True),
        )
        .order_by(Contact.created_at.desc())  # newest first
    )
    index: dict[str, Contact] = {}
    for c in rows.scalars().all():
        if not c.email:
            continue
        key = c.email.strip().lower()
        if key and key not in index:
            index[key] = c  # first occurrence wins == most recent
    logger.info(
        "email_absorber.contact_index_built user_id=%s contacts=%d",
        user_id, len(index),
    )
    return index


# ---------------------------------------------------------------------------
# Main worker
# ---------------------------------------------------------------------------


async def absorb_user_emails_task(
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory,
) -> None:
    """Top-level fire-and-forget task. Owns its own DB session.

    Never raises out. All exceptions are caught + recorded on the
    EmailAbsorptionRun row's error_message column.
    """
    settings = Settings()
    async with session_factory() as db:
        run = await db.get(EmailAbsorptionRun, run_id)
        if run is None:
            logger.error("email_absorber.run_missing run_id=%s", run_id)
            return

        try:
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            contacts_touched: set[uuid.UUID] = set()
            stats = await _absorb_inner(
                db=db,
                run=run,
                user_id=user_id,
                lookback_days=run.lookback_days,
                settings=settings,
                contacts_touched=contacts_touched,
            )

            run.scanned = stats["scanned"]
            run.matched = stats["matched"]
            run.absorbed = stats["absorbed"]
            run.skipped = stats["skipped"]
            run.contacts_touched = len(contacts_touched)
            run.status = "complete"
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(
                "email_absorber.run_complete run_id=%s user_id=%s "
                "scanned=%d matched=%d absorbed=%d skipped=%d contacts=%d",
                run_id, user_id, run.scanned, run.matched, run.absorbed,
                run.skipped, run.contacts_touched,
            )
        except Exception as exc:
            logger.exception(
                "email_absorber.run_failed run_id=%s user_id=%s err=%s",
                run_id, user_id, exc,
            )
            try:
                run.status = "failed"
                run.error_message = str(exc)[:1000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception:
                # If we can't even record the failure we've already
                # lost the trail; the exception log above is the last
                # word.
                logger.exception("email_absorber.run_failure_recording_failed")


async def _absorb_inner(
    *,
    db: AsyncSession,
    run: EmailAbsorptionRun,
    user_id: uuid.UUID,
    lookback_days: int,
    settings: Settings,
    contacts_touched: set[uuid.UUID],
) -> dict:
    """Inner worker. Lets the outer task catch the broad exception
    while we keep the happy-path tight."""
    # 1. Locate the user's Gmail account.
    gmail_rows = await db.execute(
        select(GmailAccount).where(
            GmailAccount.user_id == user_id,
            GmailAccount.is_active.is_(True),
        )
    )
    gmail_account = gmail_rows.scalars().first()
    if gmail_account is None:
        raise ValueError("No active Gmail account connected for user")

    user_email = (gmail_account.email or "").strip().lower()
    if not user_email:
        raise ValueError("Gmail account has no email recorded")

    service = await _get_gmail_service(gmail_account, settings)

    # 2. Build the contact index.
    contact_index = await _build_contact_index(db, user_id)
    if not contact_index:
        logger.info(
            "email_absorber.no_eligible_contacts user_id=%s — nothing to absorb",
            user_id,
        )
        return {"scanned": 0, "matched": 0, "absorbed": 0, "skipped": 0}

    # 3. Determine the lookback start date.
    capped_days = min(max(lookback_days, 1), MAX_LOOKBACK_DAYS)
    requested_start = datetime.now(timezone.utc) - timedelta(days=capped_days)
    if gmail_account.absorption_last_run_at is not None:
        # Subsequent runs: max(last_run - 1 day, lookback floor). The
        # 1-day overlap catches messages that arrived during a previous
        # scan.
        cursor_start = gmail_account.absorption_last_run_at - timedelta(days=1)
        if cursor_start.tzinfo is None:
            cursor_start = cursor_start.replace(tzinfo=timezone.utc)
        after_date = max(requested_start, cursor_start)
    else:
        after_date = requested_start

    gmail_query = f"after:{after_date.strftime('%Y/%m/%d')}"
    logger.info(
        "email_absorber.gmail_query user_id=%s query=%r", user_id, gmail_query,
    )

    # 4. Iterate Gmail message pages.
    semaphore = asyncio.Semaphore(ANTHROPIC_CONCURRENCY)
    scanned = 0
    matched = 0
    absorbed = 0
    skipped = 0

    page_token: str | None = None
    while True:
        list_kwargs: dict = {
            "userId": "me",
            "q": gmail_query,
            "maxResults": 100,
        }
        if page_token:
            list_kwargs["pageToken"] = page_token

        page = service.users().messages().list(**list_kwargs).execute()
        message_refs = page.get("messages", [])
        if not message_refs:
            break

        # Process this page sequentially (Gmail throttles aggressive
        # concurrent gets), but summarization across the page can
        # parallelize under the semaphore.
        page_tasks = []
        for ref in message_refs:
            scanned += 1
            msg_id = ref["id"]

            # Idempotency check — skip if we already absorbed this
            # message for this user.
            existing = await db.execute(
                select(AbsorbedEmail.id).where(
                    AbsorbedEmail.user_id == user_id,
                    AbsorbedEmail.gmail_message_id == msg_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            # Fetch full message + match headers.
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
            except Exception as exc:
                logger.warning(
                    "email_absorber.fetch_failed user_id=%s msg_id=%s err=%s",
                    user_id, msg_id, str(exc)[:200],
                )
                skipped += 1
                continue

            headers = msg.get("payload", {}).get("headers", [])
            from_raw = _extract_header(headers, "From")
            to_raw = _extract_header(headers, "To")
            cc_raw = _extract_header(headers, "Cc")

            from_email = _extract_email_address(from_raw)
            to_emails = _extract_email_list(to_raw) + _extract_email_list(cc_raw)

            # Determine direction + contact match.
            matched_contact: Contact | None = None
            direction: str | None = None
            if from_email == user_email:
                # Outbound from user → look for a contact in recipients.
                for addr in to_emails:
                    if addr in contact_index:
                        matched_contact = contact_index[addr]
                        direction = "outbound"
                        break
            else:
                # Inbound → look for a contact in From.
                if from_email and from_email in contact_index:
                    matched_contact = contact_index[from_email]
                    direction = "inbound"

            if matched_contact is None or direction is None:
                # No CRM contact matches — privacy guarantee: do NOT
                # read or store the body of unmatched emails.
                continue

            matched += 1

            subject = _extract_header(headers, "Subject")
            date_raw = _extract_header(headers, "Date")
            sent_at: datetime | None = None
            if date_raw:
                try:
                    sent_at = parsedate_to_datetime(date_raw)
                    if sent_at.tzinfo is None:
                        sent_at = sent_at.replace(tzinfo=timezone.utc)
                except Exception:
                    sent_at = None
            if sent_at is None:
                # Gmail's internalDate (ms since epoch) is a reliable
                # fallback.
                internal_ms = msg.get("internalDate")
                if internal_ms:
                    sent_at = datetime.fromtimestamp(
                        int(internal_ms) / 1000.0, tz=timezone.utc,
                    )
            if sent_at is None:
                sent_at = datetime.now(timezone.utc)

            snippet = msg.get("snippet") or ""
            body_text = _extract_body_text(msg.get("payload", {}))
            thread_id = msg.get("threadId") or msg_id

            # Summarize under the concurrency semaphore. Wrap in a
            # nested coroutine so we can gather them per-page.
            async def _process_one(
                _msg_id=msg_id,
                _subject=subject,
                _from_addr=from_email or "",
                _to_addrs=to_emails,
                _direction=direction,
                _body=body_text,
                _snippet=snippet,
                _sent_at=sent_at,
                _thread_id=thread_id,
                _contact=matched_contact,
            ):
                async with semaphore:
                    extracted: dict | None = None
                    try:
                        extracted = await _summarize_email(
                            subject=_subject,
                            from_addr=_from_addr,
                            to_addrs=_to_addrs,
                            direction=_direction,
                            body_text=_body,
                            settings=settings,
                        )
                    except Exception as exc:
                        logger.warning(
                            "email_absorber.summary_failed user_id=%s msg_id=%s err=%s",
                            user_id, _msg_id, str(exc)[:200],
                        )
                        extracted = None

                # Persist outside the semaphore so the DB write isn't
                # bottlenecked on AI concurrency.
                memory_id: uuid.UUID | None = None
                if extracted is not None:
                    memory = ContactMemory(
                        id=uuid.uuid4(),
                        contact_id=_contact.id,
                        user_id=user_id,
                        source_type="email",
                        source_id=None,
                        summary=extracted["summary"],
                        commitments=extracted["commitments"],
                        cares_about=extracted["cares_about"],
                        talking_points=extracted["talking_points"],
                        raw_input=_body[:CLAUDE_BODY_MAX_CHARS] if _body else None,
                    )
                    db.add(memory)
                    memory_id = memory.id

                absorbed_row = AbsorbedEmail(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    contact_id=_contact.id,
                    gmail_message_id=_msg_id,
                    thread_id=_thread_id,
                    direction=_direction,
                    subject=_subject,
                    snippet=_snippet,
                    body_summary=extracted["summary"] if extracted else None,
                    sent_at=_sent_at,
                    memory_id=memory_id,
                )
                db.add(absorbed_row)
                contacts_touched.add(_contact.id)
                return True

            page_tasks.append(_process_one())

        # Run the page's process_one batch with concurrency-controlled
        # summarization. Commit at end of page so progress is visible
        # mid-run via the polling endpoint.
        if page_tasks:
            results = await asyncio.gather(*page_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.warning(
                        "email_absorber.process_failed err=%s", str(r)[:200],
                    )
                    skipped += 1
                else:
                    absorbed += 1

            # Invalidate brief caches for each contact we wrote a memory
            # for this page. One-shot per contact even if multiple
            # emails landed in this page.
            try:
                from app.contacts.ai_brief import invalidate_brief_cache
                for cid in contacts_touched:
                    await invalidate_brief_cache(db, cid)
            except Exception:
                logger.exception("email_absorber.brief_invalidate_failed")

            # Update run counters in-place so the polling endpoint
            # sees progress mid-run.
            run.scanned = scanned
            run.matched = matched
            run.absorbed = absorbed
            run.skipped = skipped
            run.contacts_touched = len(contacts_touched)
            await db.commit()

        page_token = page.get("nextPageToken")
        if not page_token:
            break

    # Persist the absorption cursor so subsequent runs only do the delta.
    gmail_account.absorption_last_run_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "scanned": scanned,
        "matched": matched,
        "absorbed": absorbed,
        "skipped": skipped,
    }
