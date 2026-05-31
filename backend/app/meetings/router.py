"""FastAPI router for the meetings module."""

import asyncio
import io
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.exceptions import ValidationError
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role
from app.documents.storage import LocalStorage, StorageBackend
from app.meetings import service
from app.meetings.models import (
    Meeting, MeetingQuoteDraft, MeetingRecording, MeetingStatus,
    MeetingSummary, QuoteDraftStatus, RecordingStatus,
    RecordingTranscript, SummaryStatus, TranscriptStatus,
)
from app.meetings.schemas import (
    GuestJoinRequest,
    InstantMeetingCreate,
    LobbyKnockRequest,
    LobbyKnockResponse,
    LobbyStatusPollResponse,
    MeetingCreate,
    MeetingListItem,
    MeetingParticipantAdd,
    MeetingParticipantResponse,
    MeetingRecordingResponse,
    MeetingResponse,
    MeetingUpdate,
    PublicMeetingInfo,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency: storage backend
# ---------------------------------------------------------------------------


def get_storage(request: Request) -> StorageBackend:
    """Resolve the storage backend from application settings."""
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)


# ---------------------------------------------------------------------------
# Meeting CRUD endpoints
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Commit 11 — Transcript endpoint
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_meeting_transcripts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Commit 13 — full-text search across the user's meeting
    transcripts. Returns meeting_id + title + a 200-char snippet
    centered on the first match.

    Uses ILIKE for engine-agnostic matching (SQLite + Postgres);
    a tsvector index can be added in a Postgres-conditional migration
    later if perf becomes an issue (single-tenant accounting practice
    is unlikely to outgrow this at any plausible volume).

    Scoped to meetings the caller owns — non-host transcripts never
    leak.
    """
    from sqlalchemy import or_, and_

    pattern = f"%{q}%"
    rows = await db.execute(
        select(RecordingTranscript, Meeting)
        .join(Meeting, RecordingTranscript.meeting_id == Meeting.id)
        .where(
            and_(
                Meeting.created_by == current_user.id,
                RecordingTranscript.status == TranscriptStatus.AVAILABLE,
                or_(
                    RecordingTranscript.full_text.ilike(pattern),
                ),
            )
        )
        .order_by(RecordingTranscript.created_at.desc())
        .limit(limit)
    )

    results = []
    q_lower = q.lower()
    for transcript, meeting in rows.all():
        text = transcript.full_text or ""
        idx = text.lower().find(q_lower)
        if idx < 0:
            continue
        # 200-char snippet centered on the match, with ellipses where
        # truncated. Keeps the UI predictable in width.
        start = max(0, idx - 80)
        end = min(len(text), idx + len(q) + 120)
        snippet = text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"

        # Best-effort segment lookup — find the segment whose text
        # contains the match; surface the timestamp so the UI can
        # jump to it.
        match_time: float | None = None
        for seg in (transcript.segments_json or []):
            if q_lower in (seg.get("text") or "").lower():
                match_time = seg.get("start")
                break

        results.append({
            "meeting_id": str(meeting.id),
            "meeting_title": meeting.title,
            "meeting_slug": meeting.slug,
            "snippet": snippet,
            "match_time_seconds": match_time,
            "scheduled_start": meeting.scheduled_start.isoformat() if meeting.scheduled_start else None,
        })

    return {"data": results, "meta": {"query": q, "total": len(results)}}


@router.get("/{meeting_id}/prior-context")
async def get_meeting_prior_context(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Commit 17 — cross-meeting context. Returns prior meeting +
    recent action items + recent topics for the linked contact.

    Returns {"data": {}} when the meeting has no contact_id — UI uses
    this to hide the section.
    """
    meeting = await service.get_meeting(db, meeting_id, current_user)
    from app.meetings.cross_context import get_prior_context_for_meeting
    payload = await get_prior_context_for_meeting(db, meeting)
    return {"data": payload}


@router.get("/{meeting_id}/quote-draft")
async def get_meeting_quote_draft(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Commit 15 — return the AI-drafted proposal/quote for the
    meeting's latest summary, if any. 404 when no draft exists.

    Auth: host-only (via service.get_meeting). Quote drafts contain
    pricing data; never expose to participants.
    """
    meeting = await service.get_meeting(db, meeting_id, current_user)
    rows = await db.execute(
        select(MeetingQuoteDraft)
        .where(MeetingQuoteDraft.meeting_id == meeting.id)
        .order_by(MeetingQuoteDraft.created_at.desc())
    )
    draft = rows.scalars().first()
    if draft is None:
        raise HTTPException(status_code=404, detail="No quote draft yet")
    return {
        "data": {
            "id": str(draft.id),
            "meeting_id": str(draft.meeting_id),
            "summary_id": str(draft.summary_id),
            "status": draft.status.value,
            "draft_title": draft.draft_title,
            "draft_summary": draft.draft_summary,
            "line_items": draft.line_items_json or [],
            "estimated_total": draft.estimated_total,
            "currency": draft.currency,
            "notes": draft.notes,
            "confidence": draft.confidence,
            "model_used": draft.model_used,
            "input_tokens": draft.input_tokens,
            "output_tokens": draft.output_tokens,
            "reviewed_at": draft.reviewed_at.isoformat() if draft.reviewed_at else None,
            "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
            "promoted_proposal_id": str(draft.promoted_proposal_id) if draft.promoted_proposal_id else None,
            "error_message": draft.error_message,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }
    }


@router.post("/{meeting_id}/quote-draft/review")
async def review_meeting_quote_draft(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Mark the quote draft as REVIEWED — audit trail only. Does NOT
    send anything to the client; promote-to-proposal is a separate
    endpoint to keep the review-vs-send gate distinct.
    """
    from datetime import datetime, timezone
    meeting = await service.get_meeting(db, meeting_id, current_user)
    rows = await db.execute(
        select(MeetingQuoteDraft)
        .where(MeetingQuoteDraft.meeting_id == meeting.id)
        .order_by(MeetingQuoteDraft.created_at.desc())
    )
    draft = rows.scalars().first()
    if draft is None:
        raise HTTPException(status_code=404, detail="No quote draft to review")
    if draft.status not in (
        QuoteDraftStatus.AVAILABLE, QuoteDraftStatus.REVIEWED,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot review a draft in status '{draft.status.value}'",
        )
    draft.status = QuoteDraftStatus.REVIEWED
    draft.reviewed_at = datetime.now(timezone.utc)
    draft.reviewed_by = current_user.id
    await db.commit()
    await db.refresh(draft)
    return {"data": {"reviewed_at": draft.reviewed_at.isoformat()}}


@router.get("/{meeting_id}/summary")
async def get_meeting_summary(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return the Claude-generated summary for the meeting's latest
    available transcript (Commit 12). 404 when none exists yet — the
    UI uses that to show 'summary pending' messaging."""
    meeting = await service.get_meeting(db, meeting_id, current_user)
    rows = await db.execute(
        select(MeetingSummary)
        .where(MeetingSummary.meeting_id == meeting.id)
        .order_by(MeetingSummary.created_at.desc())
    )
    summary = rows.scalars().first()
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary yet")
    return {
        "data": {
            "id": str(summary.id),
            "meeting_id": str(summary.meeting_id),
            "status": summary.status.value,
            "summary_text": summary.summary_text,
            "topics": summary.topics_json or [],
            "action_items": summary.action_items_json or [],
            "next_steps": summary.next_steps_json or [],
            "model_used": summary.model_used,
            "input_tokens": summary.input_tokens,
            "output_tokens": summary.output_tokens,
            "error_message": summary.error_message,
            "created_at": summary.created_at.isoformat() if summary.created_at else None,
            "updated_at": summary.updated_at.isoformat() if summary.updated_at else None,
        }
    }


@router.get("/{meeting_id}/transcript")
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return the latest AVAILABLE transcript for the meeting (most
    recent recording), if any. Returns 404 when no transcript exists
    yet — the UI uses this to show 'Transcript pending…' messaging."""
    # Authorize on the meeting (host-only via service.get_meeting).
    meeting = await service.get_meeting(db, meeting_id, current_user)
    rows = await db.execute(
        select(RecordingTranscript)
        .where(RecordingTranscript.meeting_id == meeting.id)
        .order_by(RecordingTranscript.created_at.desc())
    )
    transcript = rows.scalars().first()
    if transcript is None:
        raise HTTPException(status_code=404, detail="No transcript yet")
    return {
        "data": {
            "id": str(transcript.id),
            "meeting_id": str(transcript.meeting_id),
            "recording_id": str(transcript.recording_id),
            "status": transcript.status.value,
            "provider": transcript.provider,
            "full_text": transcript.full_text,
            "segments": transcript.segments_json or [],
            "language": transcript.language,
            "duration_seconds": transcript.duration_seconds,
            "error_message": transcript.error_message,
            "created_at": transcript.created_at.isoformat() if transcript.created_at else None,
            "updated_at": transcript.updated_at.isoformat() if transcript.updated_at else None,
        }
    }


# ---------------------------------------------------------------------------
# Commit 9 — Calendar invite endpoints (.ics + Google/Outlook URLs +
# re-send). All host-auth except the .ics download which uses a slug
# (already-public information).
# ---------------------------------------------------------------------------


@router.get("/public/{slug}/invite.ics")
async def download_ics(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Public .ics download — the slug is already a shareable secret,
    so this matches the same trust level as the public meeting info
    endpoint. Useful when an invitee wants to manually add the event
    to a calendar that doesn't support the auto-attached attachment
    (e.g. an Apple Mail rules issue)."""
    settings = request.app.state.settings
    meeting = await service.get_meeting_by_slug_public(db, slug)
    # We need the host's name + email to populate ORGANIZER. Look up
    # the host user; fall back to display defaults if not findable.
    from sqlalchemy import select as _select
    from app.auth.models import User as _User
    host = (await db.execute(
        _select(_User).where(_User.id == meeting.created_by)
    )).scalar_one_or_none()
    host_name = host.full_name if host else "Meeting Host"
    host_email = host.email if host else "no-reply@accountant.ocidm.io"

    from app.meetings.calendar_invite import build_ics
    body = build_ics(meeting, host_name, host_email, settings.public_base_url)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="meeting.ics"'},
    )


@router.get("/{meeting_id}/calendar-urls")
async def get_calendar_urls(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Host-side — return the add-to-Google / add-to-Outlook URLs the
    MeetingDetailPage renders as buttons. Host-only because the URL
    embeds the host's email as the implicit ORGANIZER."""
    settings = request.app.state.settings
    meeting = await service.get_meeting(db, meeting_id, current_user)
    from app.meetings.calendar_invite import (
        google_calendar_url, outlook_calendar_url,
    )
    host_email = current_user.email
    return {
        "data": {
            "google": google_calendar_url(meeting, host_email, settings.public_base_url),
            "outlook": outlook_calendar_url(meeting, host_email, settings.public_base_url),
            "ics_url": f"/api/meetings/public/{meeting.slug}/invite.ics",
        }
    }


@router.post("/{meeting_id}/send-invites")
async def send_invites(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Manually (re-)send the calendar invite to all participants on
    the meeting. Reuses the same email rendering + SMTP path as the
    automatic on-create send. Returns counts so the UI can surface
    'Sent 3 of 4 invites' partial success."""
    settings = request.app.state.settings
    meeting = await service.get_meeting(db, meeting_id, current_user)
    from app.meetings.email_invite import send_meeting_invites
    result = await send_meeting_invites(db, meeting, current_user, settings)
    return {"data": result}


# ---------------------------------------------------------------------------
# Commit 8 — Instant meeting + public slug/lobby endpoints.
#
# These are declared BEFORE the parameterized /{meeting_id} routes so
# the literal-path matches ("instant", "public/{slug}") win in
# FastAPI's path resolution.
# ---------------------------------------------------------------------------


@router.post("/instant", status_code=201)
async def create_instant_meeting(
    body: InstantMeetingCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Create-and-start in one step. Returns the meeting + a host
    token payload so the client can connect without a second round trip.

    Matches Google Meet's "+ New meeting → Start an instant meeting"
    flow — host clicks, gets a shareable URL, lands in the room.
    """
    settings = request.app.state.settings
    meeting, token_payload = await service.start_instant_meeting(
        db, current_user, settings,
        title=body.title,
        record_meeting=body.record_meeting,
        template=body.template,
    )
    return {
        "data": {
            "meeting": MeetingResponse.model_validate(meeting).model_dump(mode="json"),
            "join": token_payload,
        }
    }


@router.get("/public/{slug}")
async def public_meeting_info(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public pre-join lookup — no auth. Returns the minimal info the
    landing page needs to render: title, status, scheduled time.
    Deliberately excludes livekit_room_name, participant emails,
    recordings, etc. so a leaked slug doesn't disclose more than the
    URL already does."""
    meeting = await service.get_meeting_by_slug_public(db, slug)
    return {
        "data": PublicMeetingInfo(
            slug=meeting.slug or slug,
            title=meeting.title,
            status=meeting.status,
            scheduled_start=meeting.scheduled_start,
            record_meeting=bool(meeting.record_meeting),
        ).model_dump(mode="json")
    }


@router.post("/public/{slug}/knock", status_code=201)
async def knock_at_lobby(
    slug: str,
    body: LobbyKnockRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Guest entry point — submit name + email. Email must match an
    invited address (case-insensitive). On success, returns the lobby
    ID the guest's browser polls with."""
    try:
        participant = await service.knock_at_lobby(
            db, slug, body.name, body.email,
        )
    except ValidationError as exc:
        # Translate to 403 so the frontend can surface a friendly
        # "you're not on the invite list" inline error.
        raise HTTPException(status_code=403, detail=str(exc))
    return {
        "data": LobbyKnockResponse(
            lobby_id=participant.id,
            status=participant.lobby_status,
        ).model_dump(mode="json")
    }


@router.get("/public/{slug}/lobby/{lobby_id}")
async def poll_lobby_status(
    slug: str,
    lobby_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Polled by the guest browser ~every 3 sec. Returns 'waiting'
    until the host clicks Admit, then returns a LiveKit token the
    guest can connect with. Returns 'denied' if the host clicks Deny."""
    settings = request.app.state.settings
    payload = await service.get_lobby_status(db, slug, lobby_id, settings)
    return {"data": LobbyStatusPollResponse(**payload).model_dump(mode="json")}


@router.get("/{meeting_id}/lobby")
async def list_lobby(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Host-side — list participants currently in the lobby. The
    in-room lobby panel polls this every ~3 sec to show Admit/Deny."""
    waiting = await service.list_lobby(db, meeting_id, current_user)
    return {
        "data": [
            MeetingParticipantResponse.model_validate(p).model_dump(mode="json")
            for p in waiting
        ]
    }


@router.post("/{meeting_id}/lobby/{lobby_id}/admit")
async def admit_from_lobby(
    meeting_id: uuid.UUID,
    lobby_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    participant = await service.admit_from_lobby(
        db, meeting_id, lobby_id, current_user,
    )
    return {
        "data": MeetingParticipantResponse.model_validate(participant).model_dump(mode="json")
    }


@router.post("/{meeting_id}/lobby/{lobby_id}/deny")
async def deny_from_lobby(
    meeting_id: uuid.UUID,
    lobby_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    participant = await service.deny_from_lobby(
        db, meeting_id, lobby_id, current_user,
    )
    return {
        "data": MeetingParticipantResponse.model_validate(participant).model_dump(mode="json")
    }


# ---------------------------------------------------------------------------
# CRUD endpoints (continued)
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_meeting(
    data: MeetingCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Create a new meeting."""
    settings = request.app.state.settings
    meeting = await service.create_meeting(db, current_user, data, settings)
    return {"data": MeetingResponse.model_validate(meeting)}


@router.get("/")
async def list_meetings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: MeetingStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List meetings with optional status filter."""
    meetings, total_count = await service.list_meetings(
        db, user=current_user, status_filter=status, skip=skip, limit=limit
    )
    items = []
    for m in meetings:
        item = MeetingListItem(
            id=m.id,
            title=m.title,
            status=m.status,
            scheduled_start=m.scheduled_start,
            scheduled_end=m.scheduled_end,
            record_meeting=m.record_meeting,
            contact_id=m.contact_id,
            participant_count=len(m.participants) if m.participants else 0,
            created_at=m.created_at,
        )
        items.append(item)
    return {
        "data": [i.model_dump(mode="json") for i in items],
        "meta": {
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
        },
    }


@router.get("/recordings/all")
async def list_all_recordings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List all recordings with optional filters."""
    recordings = await service.list_recordings(
        db, meeting_id=meeting_id, contact_id=contact_id, skip=skip, limit=limit,
        user=current_user,
    )
    return {
        "data": [MeetingRecordingResponse.model_validate(r) for r in recordings],
    }


@router.get("/recordings/by-contact")
async def list_recordings_by_contact(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List recordings grouped by contact."""
    grouped = await service.list_recordings_by_contact(db, current_user)
    # Serialize recordings within each group
    result = []
    for group in grouped:
        result.append({
            "contact_id": group["contact_id"],
            "recording_count": group["recording_count"],
            "recordings": [
                MeetingRecordingResponse.model_validate(r)
                for r in group["recordings"]
            ],
        })
    return {"data": result}


@router.get("/recordings/{recording_id}/download")
async def download_recording(
    recording_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_token)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
):
    """Download a recording file. Streams from disk for local storage."""
    recording = await service.get_recording_stream_info(db, recording_id, current_user)
    if not recording.storage_path:
        raise ValidationError("Recording file is not available.")

    ext = recording.mime_type.split("/")[-1] if recording.mime_type else "webm"
    filename = f"recording-{recording.id}.{ext}"

    if hasattr(storage, "get_full_path"):
        file_path = storage.get_full_path(recording.storage_path)
        return FileResponse(
            path=str(file_path),
            media_type=recording.mime_type,
            filename=filename,
        )

    data = await storage.read(recording.storage_path)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=recording.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@router.get("/recordings/{recording_id}/stream")
async def stream_recording(
    recording_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_token)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    request: Request,
) -> StreamingResponse:
    """Stream a recording with Range header support.

    Uses file-based streaming for local storage to avoid loading
    large video files into memory.
    """
    recording = await service.get_recording_stream_info(db, recording_id, current_user)
    if not recording.storage_path:
        raise ValidationError("Recording file is not available.")

    # File-based streaming for local storage
    if hasattr(storage, "get_full_path"):
        file_path = storage.get_full_path(recording.storage_path)
        total_size = file_path.stat().st_size

        range_header = request.headers.get("range")
        if range_header:
            range_str = range_header.replace("bytes=", "")
            parts = range_str.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else total_size - 1
            end = min(end, total_size - 1)
            content_length = end - start + 1

            async def range_gen():
                chunk_size = 64 * 1024
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                range_gen(),
                status_code=206,
                media_type=recording.mime_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{total_size}",
                    "Content-Length": str(content_length),
                    "Accept-Ranges": "bytes",
                },
            )

        async def full_gen():
            chunk_size = 64 * 1024
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        return StreamingResponse(
            full_gen(),
            media_type=recording.mime_type,
            headers={
                "Content-Length": str(total_size),
                "Accept-Ranges": "bytes",
            },
        )

    # Fallback: load into memory for non-local storage
    data = await storage.read(recording.storage_path)
    total_size = len(data)

    range_header = request.headers.get("range")
    if range_header:
        range_str = range_header.replace("bytes=", "")
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else total_size - 1
        end = min(end, total_size - 1)
        content_length = end - start + 1

        return StreamingResponse(
            io.BytesIO(data[start : end + 1]),
            status_code=206,
            media_type=recording.mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
            },
        )

    return StreamingResponse(
        io.BytesIO(data),
        media_type=recording.mime_type,
        headers={
            "Content-Length": str(total_size),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{meeting_id}")
async def get_meeting(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single meeting with full details."""
    meeting = await service.get_meeting(db, meeting_id, current_user)
    return {"data": MeetingResponse.model_validate(meeting)}


@router.put("/{meeting_id}")
async def update_meeting(
    meeting_id: uuid.UUID,
    data: MeetingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Update meeting details."""
    meeting = await service.update_meeting(db, meeting_id, current_user, data)
    return {"data": MeetingResponse.model_validate(meeting)}


@router.delete("/{meeting_id}")
async def cancel_meeting(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Cancel a meeting."""
    meeting = await service.cancel_meeting(db, meeting_id, current_user)
    return {"data": MeetingResponse.model_validate(meeting)}


# ---------------------------------------------------------------------------
# Room lifecycle endpoints
# ---------------------------------------------------------------------------


@router.post("/{meeting_id}/start")
async def start_meeting(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Start a meeting and get the host's LiveKit token."""
    settings = request.app.state.settings
    result = await service.start_meeting(db, meeting_id, current_user, settings)
    return {"data": result}


@router.post("/{meeting_id}/join")
async def join_meeting(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Join an in-progress meeting as an authenticated user."""
    settings = request.app.state.settings
    token_response = await service.join_meeting(
        db, meeting_id, current_user, settings
    )
    return {"data": token_response.model_dump()}


@router.post("/{meeting_id}/join-guest")
async def join_meeting_as_guest(
    meeting_id: uuid.UUID,
    body: GuestJoinRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., description="Guest join token"),
) -> dict:
    """Join a meeting as a guest using a join token. No authentication required."""
    settings = request.app.state.settings
    token_response = await service.join_meeting_as_guest(
        db, meeting_id, token, body.guest_name, settings
    )
    return {"data": token_response.model_dump()}


@router.post("/{meeting_id}/end")
async def end_meeting(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """End a meeting."""
    settings = request.app.state.settings
    meeting = await service.end_meeting(db, meeting_id, current_user, settings)
    return {"data": MeetingResponse.model_validate(meeting)}


# ---------------------------------------------------------------------------
# Recording endpoints
# ---------------------------------------------------------------------------


@router.post("/{meeting_id}/recordings/start")
async def start_recording(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Start recording a meeting."""
    settings = request.app.state.settings
    recording = await service.start_recording(db, meeting_id, current_user, settings)
    return {"data": MeetingRecordingResponse.model_validate(recording)}


@router.post("/{meeting_id}/recordings/stop")
async def stop_recording(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
    recording_id: uuid.UUID = Query(..., description="Recording ID to stop"),
) -> dict:
    """Stop recording a meeting."""
    settings = request.app.state.settings
    recording = await service.stop_recording(db, recording_id, current_user, settings)
    return {"data": MeetingRecordingResponse.model_validate(recording)}


@router.post("/{meeting_id}/recordings/upload", status_code=201)
async def upload_recording(
    meeting_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
) -> dict:
    """Upload a client-side recorded meeting file."""
    file_data = await file.read()
    file_size = len(file_data)

    # Save file to storage
    storage_path = await storage.save(file_data, "webm")

    recording = await service.upload_recording(
        db, meeting_id, current_user, file_data, file_size, storage_path
    )
    return {"data": MeetingRecordingResponse.model_validate(recording)}


@router.get("/{meeting_id}/recordings")
async def list_meeting_recordings(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List recordings for a specific meeting."""
    recordings = await service.list_recordings(db, meeting_id=meeting_id, user=current_user)
    return {"data": [MeetingRecordingResponse.model_validate(r) for r in recordings]}


@router.delete("/recordings/{recording_id}")
async def delete_recording(
    recording_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    """Delete a recording and its file."""
    await service.delete_recording(db, recording_id, current_user, storage)
    return {"data": {"message": "Recording deleted"}}


# ---------------------------------------------------------------------------
# Participant endpoints
# ---------------------------------------------------------------------------


@router.post("/{meeting_id}/participants", status_code=201)
async def add_participant(
    meeting_id: uuid.UUID,
    data: MeetingParticipantAdd,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Add a participant to a meeting."""
    participant = await service.add_participant(db, meeting_id, current_user, data)
    return {"data": MeetingParticipantResponse.model_validate(participant)}


@router.delete("/{meeting_id}/participants/{participant_id}")
async def remove_participant(
    meeting_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
) -> dict:
    """Remove a participant from a meeting."""
    await service.remove_participant(db, meeting_id, participant_id, current_user)
    return {"data": {"message": "Participant removed successfully"}}


# ---------------------------------------------------------------------------
# LiveKit Egress webhook (Commit 7)
# ---------------------------------------------------------------------------


@router.post("/livekit-webhook", include_in_schema=False)
async def livekit_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Receive LiveKit webhook events.

    Only egress_ended / egress_updated completion events are acted on
    in this commit — we use them to flip the matching MeetingRecording
    row from RECORDING/PROCESSING to AVAILABLE with the final storage
    path + duration + size. Other event types (room_started,
    participant_joined, etc.) are accepted and 200 OK'd but ignored.

    Authorization: LiveKit signs each payload with a JWT-shaped token
    in the Authorization header. verify_webhook reconstitutes and
    HMAC-checks it; signature failures → 401.

    Idempotency: handle_egress_completion is a no-op for already-
    AVAILABLE rows, so duplicate deliveries (LiveKit retries on 5xx)
    are safe.
    """
    settings = request.app.state.settings
    raw_body = await request.body()
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )

    from app.meetings import livekit_egress
    try:
        event = livekit_egress.verify_webhook(raw_body, auth_header, settings)
    except ValidationError as exc:
        # 401 — bad signature, missing header, etc. Don't echo the
        # error text to the wire (could leak signing details).
        logger.warning("meeting.webhook_rejected reason=%s", str(exc)[:120])
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    completion = livekit_egress.extract_egress_completion(event)
    if completion is None:
        # Non-egress event, or still-running egress — accept and move on.
        return {"received": True}

    await service.handle_egress_completion(
        db,
        egress_id=completion["egress_id"],
        storage_path=completion.get("storage_path"),
        duration_seconds=completion.get("duration_seconds"),
        file_size=completion.get("file_size"),
        status=completion["status"],
        settings=settings,
    )
    return {"received": True}


# ---------------------------------------------------------------------------
# LiveKit WebSocket proxy
# ---------------------------------------------------------------------------


@router.websocket("/livekit-proxy")
async def livekit_ws_proxy(websocket: WebSocket):
    """Proxy WebSocket connections to the local LiveKit server.

    This allows the frontend to reach LiveKit through the same domain/port as
    the FastAPI backend, which is required when the hosting provider (e.g.
    DreamHost) only exposes a single port via its reverse-proxy.
    """
    import websockets

    settings = websocket.app.state.settings
    livekit_url = settings.livekit_url or "ws://localhost:7880"

    # Normalise to ws:// for local connection (backend connects locally)
    local_url = livekit_url.replace("wss://", "ws://")
    # Strip trailing slashes and ensure it's the raw host:port
    if "localhost" not in local_url and "127.0.0.1" not in local_url:
        local_url = "ws://localhost:7880"

    # Forward all query parameters (access_token, protocol, etc.)
    qs = str(websocket.url.query)
    upstream_url = f"{local_url.rstrip('/')}/rtc"
    if qs:
        upstream_url += f"?{qs}"

    conn_id = id(websocket)
    logger.info("LiveKit proxy [%s]: opening upstream %s", conn_id, upstream_url.split("?")[0])

    await websocket.accept()

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers={},
            max_size=None,
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as lk_ws:

            logger.info("LiveKit proxy [%s]: upstream connected", conn_id)

            async def client_to_livekit():
                """Forward frames from browser to LiveKit."""
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if "bytes" in msg and msg["bytes"]:
                            await lk_ws.send(msg["bytes"])
                        elif "text" in msg and msg["text"]:
                            await lk_ws.send(msg["text"])
                except Exception as exc:
                    logger.debug("LiveKit proxy [%s]: client→LK ended: %s", conn_id, exc)

            async def livekit_to_client():
                """Forward frames from LiveKit to browser."""
                try:
                    async for message in lk_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception as exc:
                    logger.debug("LiveKit proxy [%s]: LK→client ended: %s", conn_id, exc)

            # Run both directions concurrently
            tasks = [
                asyncio.create_task(client_to_livekit(), name=f"c2lk-{conn_id}"),
                asyncio.create_task(livekit_to_client(), name=f"lk2c-{conn_id}"),
            ]

            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the remaining tasks
            for task in pending:
                task.cancel()

            logger.info("LiveKit proxy [%s]: connection closed", conn_id)

    except Exception:
        logger.warning("LiveKit proxy [%s]: connection error", conn_id, exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/webhooks/livekit")
async def livekit_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Handle LiveKit webhook events. No auth -- validated via LiveKit signature."""
    settings = request.app.state.settings
    body = await request.body()

    # Validate webhook signature
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing webhook authorization")

    try:
        from livekit.api import WebhookReceiver

        receiver = WebhookReceiver(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        event = receiver.receive(body.decode("utf-8"), auth_header)
    except Exception:
        logger.warning("Invalid LiveKit webhook signature", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Process webhook events
    event_type = getattr(event, "event", None)
    logger.info("Received LiveKit webhook event: %s", event_type)

    if event_type == "egress_ended":
        # Update recording status when egress completes
        egress_info = getattr(event, "egress_info", None)
        if egress_info:
            egress_id = egress_info.egress_id
            result = await db.execute(
                select(MeetingRecording).where(
                    MeetingRecording.egress_id == egress_id
                )
            )
            recording = result.scalar_one_or_none()
            if recording:
                # Check if egress was successful
                egress_status = getattr(egress_info, "status", None)
                if egress_status and str(egress_status) == "EGRESS_COMPLETE":
                    recording.status = RecordingStatus.AVAILABLE
                    # Try to get file info from egress
                    file_results = getattr(egress_info, "file_results", None)
                    if file_results:
                        recording.storage_path = getattr(
                            file_results, "filename", None
                        )
                        recording.file_size = getattr(
                            file_results, "size", None
                        )
                        recording.duration_seconds = int(
                            getattr(file_results, "duration", 0)
                        )
                else:
                    recording.status = RecordingStatus.FAILED

                await db.commit()

    return {"data": {"message": "Webhook processed"}}
