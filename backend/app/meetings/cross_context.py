"""Cross-meeting context (Commit 17).

For meetings linked to a contact, surface:
  - The most recent previous meeting with the same contact (title +
    date + one-line summary)
  - Recent action items extracted from prior meetings (max ~5)
  - Recent topics discussed (max ~5)

Used in two places:
  - MeetingDetailPage above the calendar invite (so the host opens
    a meeting and immediately sees what was last discussed)
  - Pre-join screen for scheduled meetings (future commit)

Closes the loop: every previous meeting's AI summary is automatically
mineable context for the next one. Granola does a basic version of
this; we have the advantage of also pulling action items from the
contact timeline (Commit 14).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contacts.models import ActivityType, ContactActivity
from app.meetings.models import (
    Meeting, MeetingStatus, MeetingSummary, SummaryStatus,
)

logger = logging.getLogger(__name__)


async def get_prior_context_for_meeting(
    db: AsyncSession,
    meeting: Meeting,
    *,
    action_item_limit: int = 5,
    topic_limit: int = 5,
) -> dict:
    """Build the prior-context payload for one meeting.

    Returns {} when the meeting has no contact_id (no cross-meeting
    context to surface). Returns structured data otherwise — the
    router serializes it for the frontend.
    """
    if meeting.contact_id is None:
        return {}

    # 1. Last prior meeting (any status except this one).
    prior_q = await db.execute(
        select(Meeting)
        .where(
            and_(
                Meeting.contact_id == meeting.contact_id,
                Meeting.id != meeting.id,
                Meeting.status.in_([
                    MeetingStatus.COMPLETED, MeetingStatus.IN_PROGRESS,
                ]),
            )
        )
        .order_by(Meeting.actual_start.desc(), Meeting.scheduled_start.desc())
        .limit(1)
    )
    prior_meeting: Meeting | None = prior_q.scalar_one_or_none()

    last_meeting_payload: dict | None = None
    if prior_meeting is not None:
        # Find its latest AVAILABLE summary, if any
        ms_q = await db.execute(
            select(MeetingSummary)
            .where(
                and_(
                    MeetingSummary.meeting_id == prior_meeting.id,
                    MeetingSummary.status == SummaryStatus.AVAILABLE,
                )
            )
            .order_by(MeetingSummary.created_at.desc())
            .limit(1)
        )
        prior_summary: MeetingSummary | None = ms_q.scalar_one_or_none()
        last_meeting_payload = {
            "id": str(prior_meeting.id),
            "title": prior_meeting.title,
            "scheduled_start": (
                prior_meeting.scheduled_start.isoformat()
                if prior_meeting.scheduled_start else None
            ),
            "actual_end": (
                prior_meeting.actual_end.isoformat()
                if prior_meeting.actual_end else None
            ),
            "summary_text": prior_summary.summary_text if prior_summary else None,
        }

    # 2. Recent action items — from ContactActivity rows we created in
    # Commit 14. We sort by created_at desc and take the most recent.
    action_q = await db.execute(
        select(ContactActivity)
        .where(
            and_(
                ContactActivity.contact_id == meeting.contact_id,
                ContactActivity.reference_type == "meeting_summary",
                ContactActivity.activity_type == ActivityType.NOTE_ADDED,
            )
        )
        .order_by(ContactActivity.created_at.desc())
        .limit(action_item_limit)
    )
    recent_action_items = [
        {
            "title": a.title,
            "description": a.description,
            "source_summary_id": str(a.reference_id) if a.reference_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in action_q.scalars().all()
    ]

    # 3. Recent topics — pulled from the prior meeting's summary.
    recent_topics: list[dict] = []
    if prior_meeting is not None:
        ms_q2 = await db.execute(
            select(MeetingSummary)
            .where(
                and_(
                    MeetingSummary.meeting_id == prior_meeting.id,
                    MeetingSummary.status == SummaryStatus.AVAILABLE,
                )
            )
            .order_by(MeetingSummary.created_at.desc())
            .limit(1)
        )
        prior_summary2 = ms_q2.scalar_one_or_none()
        if prior_summary2 is not None and prior_summary2.topics_json:
            recent_topics = list(prior_summary2.topics_json)[:topic_limit]

    return {
        "contact_id": str(meeting.contact_id),
        "last_meeting": last_meeting_payload,
        "recent_action_items": recent_action_items,
        "recent_topics": recent_topics,
    }
