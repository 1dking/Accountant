"""Meeting → Contact timeline sync (Commit 14).

When a meeting ends, log a MEETING_COMPLETED activity on the contact's
timeline. When the AI summary completes, log one NOTE_ADDED activity
per extracted action item so the host's contact dashboard shows
follow-up work without needing a separate Task model.

This is the first Accountant-vertical wedge in the Direction-B
pipeline — it converts meetings (which any video product can do) into
contact-scoped work product (which Google Meet + Granola can't,
because they don't own the CRM).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contacts.models import ActivityType, ContactActivity
from app.meetings.models import Meeting, MeetingSummary

logger = logging.getLogger(__name__)


async def log_meeting_completed(
    db: AsyncSession,
    meeting: Meeting,
) -> ContactActivity | None:
    """Create a MEETING_COMPLETED row on the contact's timeline.

    No-op when the meeting has no contact_id (internal sync, ad-hoc
    instant meeting without a client tag). Idempotent — multiple calls
    return the existing row.
    """
    if meeting.contact_id is None:
        return None

    # Idempotency — only one MEETING_COMPLETED row per meeting.
    existing = await db.execute(
        select(ContactActivity).where(
            ContactActivity.contact_id == meeting.contact_id,
            ContactActivity.reference_type == "meeting",
            ContactActivity.reference_id == meeting.id,
            ContactActivity.activity_type == ActivityType.MEETING_COMPLETED,
        )
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row is not None:
        return existing_row

    duration_text = ""
    if meeting.actual_start and meeting.actual_end:
        delta = meeting.actual_end - meeting.actual_start
        mins = int(delta.total_seconds() // 60)
        duration_text = f" · {mins} min"

    row = ContactActivity(
        contact_id=meeting.contact_id,
        activity_type=ActivityType.MEETING_COMPLETED,
        title=f"Met: {meeting.title}{duration_text}",
        description=meeting.description,
        reference_type="meeting",
        reference_id=meeting.id,
        created_by=meeting.created_by,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "meeting.contact_timeline_logged meeting_id=%s contact_id=%s",
        meeting.id, meeting.contact_id,
    )
    return row


async def log_action_items_from_summary(
    db: AsyncSession,
    meeting: Meeting,
    summary: MeetingSummary,
) -> int:
    """Create NOTE_ADDED rows for each AI-extracted action item.

    Returns the count of rows created. No-op when the meeting has no
    contact_id, or when the summary has no action items, or when
    action items have already been logged for this summary (idempotent).
    """
    if meeting.contact_id is None:
        return 0
    items = summary.action_items_json or []
    if not items:
        return 0

    # Idempotency — check if action items for this summary have already
    # been logged. We tag them via reference_type="meeting_summary".
    # There can be many rows per summary (one per item) so use .first().
    existing = await db.execute(
        select(ContactActivity.id).where(
            ContactActivity.contact_id == meeting.contact_id,
            ContactActivity.reference_type == "meeting_summary",
            ContactActivity.reference_id == summary.id,
        ).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return 0  # already logged

    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        assignee = item.get("assignee")
        due_hint = item.get("due_hint")
        # Compact description so it reads cleanly inline:
        #   "Send Q3 proposal — Alice · by Friday"
        suffix_parts = []
        if assignee:
            suffix_parts.append(str(assignee))
        if due_hint:
            suffix_parts.append(f"by {due_hint}")
        suffix = " · ".join(suffix_parts)
        description = f"{text} — {suffix}" if suffix else text
        row = ContactActivity(
            contact_id=meeting.contact_id,
            activity_type=ActivityType.NOTE_ADDED,
            title=f"Action: {text[:120]}",
            description=description,
            reference_type="meeting_summary",
            reference_id=summary.id,
            created_by=meeting.created_by,
        )
        db.add(row)
        count += 1
    await db.commit()
    logger.info(
        "meeting.action_items_logged meeting_id=%s contact_id=%s count=%d",
        meeting.id, meeting.contact_id, count,
    )
    return count
