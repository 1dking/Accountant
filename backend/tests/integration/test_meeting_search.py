"""Commit 13 — searchable transcript across meetings.

Covers:
  - search returns matches across the user's own meetings only
  - snippet centered on the first match, with ellipses for truncation
  - match_time_seconds populated from the first matching segment
  - case-insensitive
  - non-matching query returns empty list
  - PROCESSING/FAILED transcripts are excluded (no leaking partial state)
  - other-user's transcripts are excluded (scoped to current_user)
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings.models import (
    Meeting, MeetingRecording, RecordingStatus, RecordingTranscript,
    TranscriptStatus,
)


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="alice@example.com",
        hashed_password=hash_password("x"),
        full_name="Alice", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def other_host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="bob@example.com",
        hashed_password=hash_password("x"),
        full_name="Bob", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _make_meeting_with_transcript(
    db: AsyncSession, host: User, title: str, text: str,
    *, status: TranscriptStatus = TranscriptStatus.AVAILABLE,
    segments: list | None = None,
) -> Meeting:
    m = Meeting(
        id=uuid.uuid4(), title=title,
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"r-{uuid.uuid4().hex[:8]}",
        created_by=host.id, slug=f"s-{uuid.uuid4().hex[:8]}",
    )
    db.add(m)
    rec = MeetingRecording(
        id=uuid.uuid4(), meeting_id=m.id,
        status=RecordingStatus.AVAILABLE,
        storage_path="x", mime_type="video/mp4", started_by=host.id,
    )
    db.add(rec)
    await db.flush()
    t = RecordingTranscript(
        meeting_id=m.id, recording_id=rec.id,
        status=status, full_text=text,
        segments_json=segments or [],
        provider="assemblyai", provider_id="X",
    )
    db.add(t)
    await db.commit()
    await db.refresh(m)
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_search_finds_match_in_own_meeting(
    db: AsyncSession, host: User,
):
    m = await _make_meeting_with_transcript(
        db, host,
        "Acme client review",
        "We discussed Q3 cash flow and the proposed pricing increase for Acme.",
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="pricing", limit=10,
    )
    data = result["data"]
    assert len(data) == 1
    assert data[0]["meeting_id"] == str(m.id)
    assert "pricing" in data[0]["snippet"].lower()


@pytest.mark.high
async def test_search_is_case_insensitive(db: AsyncSession, host: User):
    await _make_meeting_with_transcript(
        db, host, "x", "Q3 PRICING discussion.",
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="pricing", limit=10,
    )
    assert len(result["data"]) == 1


@pytest.mark.high
async def test_search_returns_match_time_from_segment(
    db: AsyncSession, host: User,
):
    """When the transcript has segments, surface the timestamp of the
    first segment containing the query. UI uses this to jump-to-time."""
    await _make_meeting_with_transcript(
        db, host, "x",
        "Lots of intro chatter. Then later: cash flow discussion. End.",
        segments=[
            {"start": 0.0, "end": 12.5, "text": "Lots of intro chatter.", "speaker": "A"},
            {"start": 12.5, "end": 38.0, "text": "Then later: cash flow discussion.", "speaker": "B"},
            {"start": 38.0, "end": 41.0, "text": "End.", "speaker": "A"},
        ],
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="cash flow", limit=10,
    )
    assert result["data"][0]["match_time_seconds"] == 12.5


@pytest.mark.high
async def test_search_excludes_other_users_meetings(
    db: AsyncSession, host: User, other_host: User,
):
    """RLS-like scoping — the user can only search their own meetings."""
    await _make_meeting_with_transcript(
        db, host, "Alice's meeting", "Discussion about cash flow.",
    )
    await _make_meeting_with_transcript(
        db, other_host, "Bob's meeting", "Discussion about cash flow.",
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="cash flow", limit=10,
    )
    titles = [r["meeting_title"] for r in result["data"]]
    assert "Alice's meeting" in titles
    assert "Bob's meeting" not in titles


@pytest.mark.normal
async def test_search_excludes_non_available_transcripts(
    db: AsyncSession, host: User,
):
    """PROCESSING / FAILED transcripts are partial / unreliable; never
    return them as search hits."""
    await _make_meeting_with_transcript(
        db, host, "Pending", "Q3 pricing in progress.",
        status=TranscriptStatus.PROCESSING,
    )
    await _make_meeting_with_transcript(
        db, host, "Failed", "Q3 pricing failed.",
        status=TranscriptStatus.FAILED,
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="pricing", limit=10,
    )
    assert result["data"] == []


@pytest.mark.normal
async def test_search_no_matches_returns_empty(db: AsyncSession, host: User):
    await _make_meeting_with_transcript(
        db, host, "x", "Hello world.",
    )
    from app.meetings.router import search_meeting_transcripts
    result = await search_meeting_transcripts(
        db=db, current_user=host, q="nonexistent", limit=10,
    )
    assert result["data"] == []
    assert result["meta"]["query"] == "nonexistent"
