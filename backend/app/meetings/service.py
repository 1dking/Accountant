"""Business logic for the meetings module."""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.collaboration.service import log_activity
from app.config import Settings
from app.core.authorization import apply_ownership_filter, authorize_owner
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.meetings.models import (
    LobbyStatus,
    Meeting,
    MeetingParticipant,
    MeetingRecording,
    MeetingStatus,
    MeetingTemplate,
    ParticipantRole,
    RecordingStatus,
)


# Commit 16 — Template-driven defaults applied at create time when the
# caller doesn't explicitly override. Keep the data simple: just what
# the template would have selected on the picker, no AI prompt
# overrides here (those live in summarization/quote_draft modules
# where they're closer to the place they're consumed).
TEMPLATE_DEFAULTS = {
    MeetingTemplate.DISCOVERY_CALL: {"record_meeting_default": True},
    MeetingTemplate.CLIENT_REVIEW:  {"record_meeting_default": True},
    MeetingTemplate.INTERNAL_SYNC:  {"record_meeting_default": False},
    MeetingTemplate.GENERIC:        {"record_meeting_default": False},
}
from app.meetings.schemas import (
    JoinTokenResponse,
    MeetingCreate,
    MeetingParticipantAdd,
    MeetingUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LiveKit helpers
# ---------------------------------------------------------------------------


def _get_livekit_api(settings: Settings):
    """Create LiveKit API client. Raise ValidationError if not configured."""
    try:
        from livekit.api import LiveKitAPI
    except ModuleNotFoundError:
        raise ValidationError("LiveKit SDK is not installed.")

    if not settings.livekit_url or not settings.livekit_api_key:
        raise ValidationError("LiveKit is not configured.")
    return LiveKitAPI(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )


def generate_livekit_token(
    room_name: str,
    identity: str,
    settings: Settings,
    name: str = "",
) -> str:
    """Generate a LiveKit access token JWT."""
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise ValidationError(
            "LiveKit is not configured. Set LIVEKIT_API_KEY and LIVEKIT_API_SECRET in .env"
        )
    from livekit.api import AccessToken

    try:
        from livekit.api import VideoGrants
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )
    except ImportError:
        from livekit.api import VideoGrant
        grant = VideoGrant(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )

    token = AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
    token.with_identity(identity)
    if name:
        try:
            token.with_name(name)
        except (AttributeError, TypeError):
            pass  # older livekit-api versions may not support with_name
    token.with_grants(grant)
    return token.to_jwt()


# ---------------------------------------------------------------------------
# Meeting CRUD
# ---------------------------------------------------------------------------


_SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz"  # l, o removed (ambiguous)


def _generate_slug() -> str:
    """Generate an unverified slug — abc-defg-hij. Caller is responsible
    for collision-retry against the DB."""
    s = "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(10))
    return f"{s[0:3]}-{s[3:7]}-{s[7:10]}"


async def _generate_unique_slug(db: AsyncSession, max_tries: int = 8) -> str:
    """Generate a slug guaranteed not to collide with an existing row.
    Eight tries at ~50 bits of entropy is more than enough; we raise on
    the (mathematically impossible) eighth-collision case to surface a
    real bug if it ever happens."""
    for _ in range(max_tries):
        candidate = _generate_slug()
        existing = await db.execute(
            select(Meeting.id).where(Meeting.slug == candidate)
        )
        if existing.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Could not generate a unique meeting slug after 8 tries")


async def create_meeting(
    db: AsyncSession,
    user: User,
    data: MeetingCreate,
    settings: Settings,
) -> Meeting:
    """Create a new meeting with host participant and optional guest invites.

    Commit 8 — scheduled_start is now optional. When omitted, the
    meeting is treated as a draft that hasn't been scheduled yet; the
    host can still share the slug URL. For "start right now," use
    start_instant_meeting which both creates and starts in one step.
    """
    room_name = f"meeting-{uuid.uuid4().hex[:16]}"
    slug = await _generate_unique_slug(db)

    # Commit 16 — template-driven defaults. If the caller omitted
    # record_meeting (default False) but picked a template that
    # implies recording (e.g. DISCOVERY_CALL), promote it to True.
    record_meeting = data.record_meeting
    template = getattr(data, "template", MeetingTemplate.GENERIC)
    if not record_meeting and template in TEMPLATE_DEFAULTS:
        record_meeting = TEMPLATE_DEFAULTS[template]["record_meeting_default"]

    meeting = Meeting(
        title=data.title,
        description=data.description,
        status=MeetingStatus.SCHEDULED,
        slug=slug,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        livekit_room_name=room_name,
        record_meeting=record_meeting,
        template=template,
        created_by=user.id,
        contact_id=data.contact_id,
    )
    db.add(meeting)
    await db.flush()

    # Create host participant
    host_participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=user.id,
        role=ParticipantRole.HOST,
    )
    db.add(host_participant)

    # Create participants for each invited email
    for email in data.participant_emails:
        participant = MeetingParticipant(
            meeting_id=meeting.id,
            guest_email=email,
            role=ParticipantRole.PARTICIPANT,
            join_token=secrets.token_urlsafe(32),
        )
        db.add(participant)

    await db.commit()
    await db.refresh(meeting)

    # Reload with relationships
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.recordings),
        )
        .where(Meeting.id == meeting.id)
    )
    meeting = result.scalar_one()

    await log_activity(
        db,
        user_id=user.id,
        action="created",
        resource_type="meeting",
        resource_id=str(meeting.id),
        details={"title": meeting.title},
    )

    # Commit 9 — fire-and-forget the invite emails when the caller
    # asked for them AND there are participants to invite. Failures
    # here log loudly but never raise; the host can re-send manually
    # via POST /meetings/{id}/send-invites if anything goes wrong.
    if data.create_calendar_event and meeting.participants:
        try:
            from app.meetings.email_invite import send_meeting_invites
            await send_meeting_invites(db, meeting, user, settings)
        except Exception as exc:
            logger.warning(
                "meeting.invites_autosend_failed meeting_id=%s err=%s",
                meeting.id, str(exc)[:200],
            )

    return meeting


async def get_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
) -> Meeting:
    """Get a single meeting by ID with relationships loaded."""
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.recordings),
        )
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(meeting_id))
    authorize_owner(meeting.created_by, user, "Meeting")
    return meeting


async def list_meetings(
    db: AsyncSession,
    user: User,
    status_filter: MeetingStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Meeting], int]:
    """List meetings with optional status filter and pagination."""
    query = select(Meeting).options(
        selectinload(Meeting.participants),
    )
    query = apply_ownership_filter(query, Meeting.created_by, user)

    if status_filter is not None:
        query = query.where(Meeting.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Order by scheduled start descending
    query = query.order_by(Meeting.scheduled_start.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    meetings = list(result.scalars().unique().all())

    return meetings, total_count


async def update_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    data: MeetingUpdate,
) -> Meeting:
    """Update meeting fields."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.CANCELLED):
        raise ValidationError("Cannot update a completed or cancelled meeting.")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    await db.commit()
    await db.refresh(meeting)

    # Reload with relationships
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.recordings),
        )
        .where(Meeting.id == meeting.id)
    )
    meeting = result.scalar_one()

    await log_activity(
        db,
        user_id=user.id,
        action="updated",
        resource_type="meeting",
        resource_id=str(meeting.id),
        details={"title": meeting.title},
    )

    return meeting


async def cancel_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
) -> Meeting:
    """Cancel a meeting."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.CANCELLED):
        raise ValidationError("Meeting is already completed or cancelled.")

    meeting.status = MeetingStatus.CANCELLED
    await db.commit()
    await db.refresh(meeting)

    # Reload with relationships
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.recordings),
        )
        .where(Meeting.id == meeting.id)
    )
    meeting = result.scalar_one()

    await log_activity(
        db,
        user_id=user.id,
        action="cancelled",
        resource_type="meeting",
        resource_id=str(meeting.id),
        details={"title": meeting.title},
    )

    return meeting


# ---------------------------------------------------------------------------
# Room lifecycle
# ---------------------------------------------------------------------------


async def start_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> dict:
    """Start a meeting: create LiveKit room, update status, return host token."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status not in (MeetingStatus.SCHEDULED, MeetingStatus.IN_PROGRESS):
        raise ValidationError("Meeting cannot be started in its current state.")

    # Only create the LiveKit room when first starting (SCHEDULED → IN_PROGRESS).
    # If the meeting is already IN_PROGRESS we skip room creation because calling
    # create_room again can reset the room and disconnect existing participants.
    if meeting.status == MeetingStatus.SCHEDULED:
        lk_api = _get_livekit_api(settings)
        try:
            from livekit.api import CreateRoomRequest

            await lk_api.room.create_room(
                CreateRoomRequest(name=meeting.livekit_room_name)
            )
        except Exception:
            logger.warning(
                "LiveKit room creation failed for meeting %s, room may already exist",
                meeting.id,
                exc_info=True,
            )

        meeting.status = MeetingStatus.IN_PROGRESS
        meeting.actual_start = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(meeting)

    # Generate host token
    identity = f"user-{user.id}"
    token = generate_livekit_token(
        meeting.livekit_room_name, identity, settings,
        name=user.full_name or user.email,
    )

    # Commit 7 — auto-start server-side recording via LiveKit Egress when
    # the meeting is flagged record_meeting=True. We only kick the egress
    # off the first time the meeting transitions to IN_PROGRESS (above);
    # subsequent re-joins won't double-record because we check for an
    # existing RECORDING-state row on this meeting.
    if meeting.record_meeting:
        existing = await db.execute(
            select(MeetingRecording).where(
                MeetingRecording.meeting_id == meeting.id,
                MeetingRecording.status == RecordingStatus.RECORDING,
            )
        )
        if existing.scalar_one_or_none() is None:
            try:
                from app.meetings import livekit_egress
                egress_id, output_path = await livekit_egress.start_room_recording(
                    meeting.livekit_room_name, settings,
                )
                rec = MeetingRecording(
                    meeting_id=meeting.id,
                    status=RecordingStatus.RECORDING,
                    storage_path=output_path,
                    egress_id=egress_id,
                    mime_type="video/mp4",
                    started_by=user.id,
                )
                db.add(rec)
                await db.commit()
            except Exception as exc:
                # Don't block the meeting on recording-start failure —
                # the user can still meet, just without recording. Log
                # loudly so it shows up in monitoring.
                logger.warning(
                    "meeting.egress_autostart_failed meeting_id=%s err=%s",
                    meeting.id, str(exc)[:200],
                )

    await log_activity(
        db,
        user_id=user.id,
        action="started",
        resource_type="meeting",
        resource_id=str(meeting.id),
        details={"title": meeting.title},
    )

    return {
        "token": token,
        "room_name": meeting.livekit_room_name,
        "identity": identity,
        "record_meeting": meeting.record_meeting,
    }


async def join_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> JoinTokenResponse:
    """Join an in-progress meeting as an authenticated user."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status != MeetingStatus.IN_PROGRESS:
        raise ValidationError("Meeting is not currently in progress.")

    # Find or create participant record
    result = await db.execute(
        select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.user_id == user.id,
        )
    )
    participant = result.scalar_one_or_none()

    if participant is None:
        participant = MeetingParticipant(
            meeting_id=meeting_id,
            user_id=user.id,
            role=ParticipantRole.PARTICIPANT,
        )
        db.add(participant)

    participant.joined_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(participant)

    identity = f"user-{user.id}"
    token = generate_livekit_token(
        meeting.livekit_room_name, identity, settings,
        name=user.full_name or user.email,
    )

    return JoinTokenResponse(
        token=token,
        room_name=meeting.livekit_room_name,
        identity=identity,
        record_meeting=meeting.record_meeting,
    )


async def join_meeting_as_guest(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    join_token: str,
    guest_name: str,
    settings: Settings,
) -> JoinTokenResponse:
    """Join a meeting using a guest join token (no auth required)."""
    # Load the meeting first
    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(meeting_id))

    if meeting.status not in (MeetingStatus.SCHEDULED, MeetingStatus.IN_PROGRESS):
        raise ValidationError("Meeting is not available to join.")

    # Look up existing participant by join token
    result = await db.execute(
        select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.join_token == join_token,
        )
    )
    participant = result.scalar_one_or_none()

    if participant is None:
        # Create an ad-hoc guest participant with this token
        participant = MeetingParticipant(
            meeting_id=meeting_id,
            guest_name=guest_name,
            role=ParticipantRole.PARTICIPANT,
            join_token=join_token,
        )
        db.add(participant)
    else:
        # Update existing participant's name if provided
        if guest_name:
            participant.guest_name = guest_name

    participant.joined_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(participant)

    # Use a unique identity per connection so that sharing the same invite
    # link with multiple people doesn't cause LiveKit to kick the first
    # connection.  LiveKit treats each identity as one participant — if two
    # connections use the same identity, the first gets disconnected.
    display_name = participant.guest_name or "Guest"
    session_suffix = secrets.token_hex(4)
    identity = f"guest-{participant.id}-{session_suffix}"

    token = generate_livekit_token(
        meeting.livekit_room_name, identity, settings,
        name=display_name,
    )

    return JoinTokenResponse(
        token=token,
        room_name=meeting.livekit_room_name,
        identity=identity,
        record_meeting=meeting.record_meeting,
    )


async def end_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> Meeting:
    """End a meeting: update status and set actual_end."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status != MeetingStatus.IN_PROGRESS:
        raise ValidationError("Meeting is not currently in progress.")

    meeting.status = MeetingStatus.COMPLETED
    meeting.actual_end = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(meeting)

    # Commit 7 — stop any in-flight egresses for this meeting so the
    # MP4 finalizes and the egress_ended webhook fires. We move the
    # recording row to PROCESSING here; the webhook (or reconciliation)
    # will move it to AVAILABLE once the upload completes.
    active_recs = await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.meeting_id == meeting.id,
            MeetingRecording.status == RecordingStatus.RECORDING,
            MeetingRecording.egress_id.is_not(None),
        )
    )
    for rec in active_recs.scalars().all():
        try:
            from app.meetings import livekit_egress
            await livekit_egress.stop_room_recording(rec.egress_id, settings)
        except Exception as exc:
            logger.warning(
                "meeting.egress_stop_failed recording_id=%s err=%s",
                rec.id, str(exc)[:200],
            )
        rec.status = RecordingStatus.PROCESSING
    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.recordings),
        )
        .where(Meeting.id == meeting.id)
    )
    meeting = result.scalar_one()

    await log_activity(
        db,
        user_id=user.id,
        action="ended",
        resource_type="meeting",
        resource_id=str(meeting.id),
        details={"title": meeting.title},
    )

    # Commit 14 — log on the linked contact's timeline. Best-effort:
    # failures here don't block end_meeting. No-op when the meeting
    # has no contact_id (internal sync, ad-hoc instant call).
    try:
        from app.meetings.contact_sync import log_meeting_completed
        await log_meeting_completed(db, meeting)
    except Exception as exc:
        logger.warning(
            "meeting.contact_timeline_failed meeting_id=%s err=%s",
            meeting.id, str(exc)[:200],
        )

    return meeting


# ---------------------------------------------------------------------------
# Recordings
# ---------------------------------------------------------------------------


async def start_recording(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> MeetingRecording:
    """Mark that a recording has started (client-side MediaRecorder)."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status != MeetingStatus.IN_PROGRESS:
        raise ValidationError("Meeting must be in progress to start recording.")

    recording = MeetingRecording(
        meeting_id=meeting.id,
        status=RecordingStatus.RECORDING,
        started_by=user.id,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    await log_activity(
        db,
        user_id=user.id,
        action="started_recording",
        resource_type="meeting_recording",
        resource_id=str(recording.id),
        details={"meeting_id": str(meeting.id)},
    )

    return recording


async def stop_recording(
    db: AsyncSession,
    recording_id: uuid.UUID,
    user: User,
    settings: Settings,
) -> MeetingRecording:
    """Mark a recording as stopped (client will upload the file)."""
    result = await db.execute(
        select(MeetingRecording).where(MeetingRecording.id == recording_id)
    )
    recording = result.scalar_one_or_none()
    if recording is None:
        raise NotFoundError("MeetingRecording", str(recording_id))

    # IDOR: verify user owns the parent meeting (admins bypass)
    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == recording.meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(recording.meeting_id))
    authorize_owner(meeting.created_by, user, "MeetingRecording")

    if recording.status != RecordingStatus.RECORDING:
        raise ValidationError("Recording is not currently active.")

    recording.status = RecordingStatus.PROCESSING
    await db.commit()
    await db.refresh(recording)

    await log_activity(
        db,
        user_id=user.id,
        action="stopped_recording",
        resource_type="meeting_recording",
        resource_id=str(recording.id),
        details={"meeting_id": str(recording.meeting_id)},
    )

    return recording


async def upload_recording(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    file_data: bytes,
    file_size: int,
    storage_path: str,
) -> MeetingRecording:
    """Create a recording entry from a client-side uploaded file."""
    # Verify meeting exists
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(meeting_id))

    # IDOR: verify user owns the meeting (admins bypass)
    authorize_owner(meeting.created_by, user, "Meeting")

    recording = MeetingRecording(
        meeting_id=meeting.id,
        status=RecordingStatus.AVAILABLE,
        storage_path=storage_path,
        file_size=file_size,
        mime_type="video/webm",
        started_by=user.id,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    await log_activity(
        db,
        user_id=user.id,
        action="uploaded_recording",
        resource_type="meeting_recording",
        resource_id=str(recording.id),
        details={"meeting_id": str(meeting.id), "file_size": file_size},
    )

    return recording


async def list_recordings(
    db: AsyncSession,
    meeting_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 20,
    user: User | None = None,
) -> list[MeetingRecording]:
    """List recordings with optional meeting or contact filter."""
    query = select(MeetingRecording)

    # Always join Meeting so we can apply ownership filter
    if contact_id is not None:
        query = query.join(Meeting, MeetingRecording.meeting_id == Meeting.id).where(
            Meeting.contact_id == contact_id
        )
    else:
        query = query.join(Meeting, MeetingRecording.meeting_id == Meeting.id)

    if meeting_id is not None:
        query = query.where(MeetingRecording.meeting_id == meeting_id)

    # IDOR: only show recordings for meetings the user owns (admins bypass)
    if user is not None:
        query = apply_ownership_filter(query, Meeting.created_by, user)

    query = query.order_by(MeetingRecording.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def list_recordings_by_contact(
    db: AsyncSession,
    user: User,
) -> list[dict]:
    """List recordings grouped by contact."""
    # Get all recordings joined with meeting+contact info
    query = (
        select(
            Meeting.contact_id,
            func.count(MeetingRecording.id).label("recording_count"),
        )
        .join(Meeting, MeetingRecording.meeting_id == Meeting.id)
        .where(Meeting.contact_id.isnot(None))
    )
    # IDOR: only show recordings for meetings the user owns (admins bypass)
    query = apply_ownership_filter(query, Meeting.created_by, user)
    query = query.group_by(Meeting.contact_id).order_by(
        func.count(MeetingRecording.id).desc()
    )

    result = await db.execute(query)
    rows = result.all()

    grouped = []
    for row in rows:
        # Fetch recordings for this contact
        rec_query = (
            select(MeetingRecording)
            .join(Meeting, MeetingRecording.meeting_id == Meeting.id)
            .where(Meeting.contact_id == row.contact_id)
        )
        # IDOR: apply same ownership filter to sub-query
        rec_query = apply_ownership_filter(rec_query, Meeting.created_by, user)
        rec_query = rec_query.order_by(MeetingRecording.created_at.desc())
        rec_result = await db.execute(rec_query)
        recordings = list(rec_result.scalars().all())

        grouped.append({
            "contact_id": row.contact_id,
            "recording_count": row.recording_count,
            "recordings": recordings,
        })

    return grouped


async def get_recording_stream_info(
    db: AsyncSession,
    recording_id: uuid.UUID,
    user: User,
) -> MeetingRecording:
    """Get recording info for streaming/download."""
    result = await db.execute(
        select(MeetingRecording).where(MeetingRecording.id == recording_id)
    )
    recording = result.scalar_one_or_none()
    if recording is None:
        raise NotFoundError("MeetingRecording", str(recording_id))

    # IDOR: verify user owns the parent meeting (admins bypass)
    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == recording.meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(recording.meeting_id))
    authorize_owner(meeting.created_by, user, "MeetingRecording")

    if recording.status != RecordingStatus.AVAILABLE:
        raise ValidationError("Recording is not yet available for download.")

    return recording


async def delete_recording(
    db: AsyncSession,
    recording_id: uuid.UUID,
    user: User,
    storage: "StorageBackend",
) -> None:
    """Delete a recording and its file from storage."""
    from app.documents.storage import StorageBackend  # noqa: F811

    result = await db.execute(
        select(MeetingRecording).where(MeetingRecording.id == recording_id)
    )
    recording = result.scalar_one_or_none()
    if recording is None:
        raise NotFoundError("MeetingRecording", str(recording_id))

    # IDOR: verify user owns the parent meeting (admins bypass)
    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == recording.meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", str(recording.meeting_id))
    authorize_owner(meeting.created_by, user, "MeetingRecording")

    # Delete file from storage
    if recording.storage_path:
        try:
            await storage.delete(recording.storage_path)
        except Exception:
            pass  # file may already be gone

    await db.delete(recording)
    await db.commit()


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


async def add_participant(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    user: User,
    data: MeetingParticipantAdd,
) -> MeetingParticipant:
    """Add a participant to a meeting."""
    meeting = await get_meeting(db, meeting_id, user)

    if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.CANCELLED):
        raise ValidationError("Cannot add participants to a completed or cancelled meeting.")

    participant = MeetingParticipant(
        meeting_id=meeting_id,
        user_id=data.user_id,
        contact_id=data.contact_id,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        role=ParticipantRole(data.role),
        join_token=secrets.token_urlsafe(32),
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    await log_activity(
        db,
        user_id=user.id,
        action="added_participant",
        resource_type="meeting_participant",
        resource_id=str(participant.id),
        details={"meeting_id": str(meeting_id)},
    )

    return participant


async def remove_participant(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    participant_id: uuid.UUID,
    user: User,
) -> None:
    """Remove a participant from a meeting."""
    result = await db.execute(
        select(MeetingParticipant).where(
            MeetingParticipant.id == participant_id,
            MeetingParticipant.meeting_id == meeting_id,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise NotFoundError("MeetingParticipant", str(participant_id))

    if participant.role == ParticipantRole.HOST:
        raise ForbiddenError("Cannot remove the host from a meeting.")

    await db.delete(participant)
    await db.commit()

    await log_activity(
        db,
        user_id=user.id,
        action="removed_participant",
        resource_type="meeting_participant",
        resource_id=str(participant_id),
        details={"meeting_id": str(meeting_id)},
    )


# ---------------------------------------------------------------------------
# Commit 8 — Google-Meet-style instant + lobby flow
# ---------------------------------------------------------------------------


async def start_instant_meeting(
    db: AsyncSession,
    user: User,
    settings: Settings,
    *,
    title: str | None = None,
    record_meeting: bool = False,
    template: MeetingTemplate = MeetingTemplate.GENERIC,
) -> tuple[Meeting, dict]:
    """Create-and-start in one step. Stamps scheduled_start=now() and
    flips to IN_PROGRESS so the host can join the room URL immediately.

    Returns (meeting, host_token_payload). The host_token_payload has
    the same shape as start_meeting's return so the frontend can
    redirect into the room with one fewer round trip.

    Commit 16 — template + record_meeting plumbed through. Template
    biases the AI pipeline; record_meeting can also be set explicitly
    when the host wants recording on a generic instant call.
    """
    from app.meetings.schemas import MeetingCreate
    now = datetime.now(timezone.utc)
    data = MeetingCreate(
        title=title or "Instant meeting",
        scheduled_start=now,
        record_meeting=record_meeting,
        template=template,
        participant_emails=[],
        create_calendar_event=False,
    )
    meeting = await create_meeting(db, user, data, settings)
    token_payload = await start_meeting(db, meeting.id, user, settings)
    # Reload so the caller sees the updated status / actual_start.
    meeting = await get_meeting(db, meeting.id, user)
    return meeting, token_payload


async def get_meeting_by_slug_public(
    db: AsyncSession, slug: str,
) -> Meeting:
    """Public lookup for the pre-join page — no auth, returns the
    Meeting row but the router strips sensitive fields before serving.
    """
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.slug == slug)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting", slug)
    return meeting


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def knock_at_lobby(
    db: AsyncSession,
    slug: str,
    name: str,
    email: str,
) -> MeetingParticipant:
    """Guest entry point — verify email matches an invite, upsert a
    WAITING participant, return the lobby ID.

    Email match is case-insensitive on both sides. Re-knocking from
    the same email updates the existing row (refreshes name, resets
    DENIED → WAITING if the host wants to reconsider). Non-matching
    email → ValidationError mapped to 403 by the router.
    """
    meeting = await get_meeting_by_slug_public(db, slug)
    if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.CANCELLED):
        raise ValidationError("This meeting is not joinable.")

    target = _normalize_email(email)
    if not target:
        raise ValidationError("Email is required to knock.")

    # Find a matching participant by email. participant_emails added at
    # create-time set guest_email; an authenticated user might also be
    # invited (user_id set, no guest_email) — we'll cover that path
    # later via separate user-auth join.
    existing = None
    for p in meeting.participants:
        if p.guest_email and _normalize_email(p.guest_email) == target:
            existing = p
            break

    if existing is None:
        # Not on the invite list — Google-Meet-Workspace-style strict
        # match. Don't leak whether the meeting exists vs. just the
        # invitee list; same 403 either way.
        raise ValidationError("This email isn't on the meeting's invite list.")

    # Upsert the lobby state. Use the passed name if non-empty (lets
    # guests fix their own typos by re-knocking).
    if name and name.strip():
        existing.guest_name = name.strip()
    existing.lobby_status = LobbyStatus.WAITING
    # Bump joined_at sentinel — we use it as last-knock-at for the
    # host's lobby panel ordering. Reset on actual room join later.
    existing.joined_at = None
    existing.left_at = None
    await db.commit()
    await db.refresh(existing)
    return existing


async def get_lobby_status(
    db: AsyncSession,
    slug: str,
    lobby_id: uuid.UUID,
    settings: Settings,
) -> dict:
    """Polled by the guest browser ~every 2-3 sec while in the lobby.
    Returns a small envelope with the current state and, on ADMITTED,
    a freshly-issued LiveKit token the guest can connect with."""
    meeting = await get_meeting_by_slug_public(db, slug)
    participant = next(
        (p for p in meeting.participants if p.id == lobby_id), None,
    )
    if participant is None:
        raise NotFoundError("LobbyEntry", str(lobby_id))

    status = participant.lobby_status

    if status == LobbyStatus.DENIED:
        return {"status": "denied"}

    if status == LobbyStatus.ADMITTED:
        # Don't gate on meeting.status — host may have admitted before
        # technically pressing "start"; LiveKit handles auto-room-create
        # at first join. We still gate on COMPLETED/CANCELLED.
        if meeting.status == MeetingStatus.COMPLETED:
            return {"status": "ended"}
        if meeting.status == MeetingStatus.CANCELLED:
            return {"status": "denied"}
        # Fresh token per poll is fine — they're short-lived JWTs.
        session_suffix = secrets.token_hex(4)
        identity = f"guest-{participant.id}-{session_suffix}"
        token = generate_livekit_token(
            meeting.livekit_room_name, identity, settings,
            name=participant.guest_name or "Guest",
        )
        # Stamp joined_at the first time we hand out a token so the
        # host's UI can show "joined N min ago".
        if participant.joined_at is None:
            participant.joined_at = datetime.now(timezone.utc)
            await db.commit()
        return {
            "status": "admitted",
            "token": token,
            "room_name": meeting.livekit_room_name,
            "identity": identity,
            "record_meeting": meeting.record_meeting,
        }

    return {"status": "waiting"}


async def list_lobby(
    db: AsyncSession, meeting_id: uuid.UUID, user: User,
) -> list[MeetingParticipant]:
    """Host-side — return waiting guests so the in-room panel can show
    Admit/Deny buttons. Ordered by knock time (joined_at == None
    means "just knocked," sorted last for visibility)."""
    meeting = await get_meeting(db, meeting_id, user)
    waiting = [
        p for p in meeting.participants
        if p.lobby_status == LobbyStatus.WAITING
    ]
    return waiting


async def admit_from_lobby(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    lobby_id: uuid.UUID,
    user: User,
) -> MeetingParticipant:
    """Host approves a waiting guest. Idempotent — already-ADMITTED
    rows are returned unchanged. DENIED rows can be re-admitted by
    the host (no terminal lock)."""
    meeting = await get_meeting(db, meeting_id, user)
    participant = next(
        (p for p in meeting.participants if p.id == lobby_id), None,
    )
    if participant is None:
        raise NotFoundError("LobbyEntry", str(lobby_id))
    if participant.lobby_status not in (
        LobbyStatus.WAITING, LobbyStatus.DENIED, LobbyStatus.ADMITTED,
    ):
        raise ValidationError("Participant is not in the lobby.")
    participant.lobby_status = LobbyStatus.ADMITTED
    await db.commit()
    await db.refresh(participant)
    await log_activity(
        db, user_id=user.id, action="admitted_from_lobby",
        resource_type="meeting_participant",
        resource_id=str(participant.id),
        details={"meeting_id": str(meeting.id)},
    )
    return participant


async def deny_from_lobby(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    lobby_id: uuid.UUID,
    user: User,
) -> MeetingParticipant:
    """Host rejects a guest. Marks DENIED; the guest's poll returns
    'denied' on next tick and the frontend shows a closed-door message.
    """
    meeting = await get_meeting(db, meeting_id, user)
    participant = next(
        (p for p in meeting.participants if p.id == lobby_id), None,
    )
    if participant is None:
        raise NotFoundError("LobbyEntry", str(lobby_id))
    participant.lobby_status = LobbyStatus.DENIED
    await db.commit()
    await db.refresh(participant)
    await log_activity(
        db, user_id=user.id, action="denied_from_lobby",
        resource_type="meeting_participant",
        resource_id=str(participant.id),
        details={"meeting_id": str(meeting.id)},
    )
    return participant


# ---------------------------------------------------------------------------
# LiveKit Egress — webhook + reconciliation (Commit 7)
# ---------------------------------------------------------------------------


async def handle_egress_completion(
    db: AsyncSession,
    egress_id: str,
    storage_path: str | None,
    duration_seconds: int | None,
    file_size: int | None,
    status: str,
    settings: "Settings | None" = None,
) -> MeetingRecording | None:
    """Idempotent completion handler. Called from both the webhook
    receiver and the reconciliation job — same code path either way.

    Looks up MeetingRecording by egress_id. If found and still in
    RECORDING / PROCESSING state, transitions to AVAILABLE (or FAILED)
    and stamps the storage path + duration + file size. Already-
    AVAILABLE rows are no-ops, so calling this twice (webhook +
    reconciliation) is safe.

    Returns the row that was updated, or None if no matching row
    exists (orphan — typically a reconciliation backstop catching an
    egress for a meeting that was deleted before the egress finished).
    """
    result = await db.execute(
        select(MeetingRecording).where(MeetingRecording.egress_id == egress_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        logger.info(
            "meeting.egress_completion_orphan egress_id=%s — no recording row",
            egress_id,
        )
        return None

    # Idempotency — already terminal, nothing to do.
    if rec.status in (RecordingStatus.AVAILABLE, RecordingStatus.FAILED):
        return rec

    if status == "complete":
        rec.status = RecordingStatus.AVAILABLE
    else:
        rec.status = RecordingStatus.FAILED

    if storage_path:
        rec.storage_path = storage_path
    if duration_seconds is not None:
        rec.duration_seconds = duration_seconds
    if file_size is not None:
        rec.file_size = file_size

    await db.commit()
    await db.refresh(rec)

    logger.info(
        "meeting.egress_completed recording_id=%s egress_id=%s status=%s",
        rec.id, egress_id, rec.status.value,
    )

    # Commit 11 — when a recording becomes AVAILABLE, kick off
    # AssemblyAI transcription. submit_meeting_transcription is
    # best-effort + idempotent; failure here doesn't roll back the
    # recording-completion state change above.
    if rec.status == RecordingStatus.AVAILABLE and settings is not None:
        try:
            from app.meetings.transcription import submit_meeting_transcription
            await submit_meeting_transcription(db, rec, settings)
        except Exception as exc:
            logger.warning(
                "meeting.transcription_kickoff_failed recording_id=%s err=%s",
                rec.id, str(exc)[:200],
            )

    return rec


async def reconcile_egresses(db: AsyncSession, settings: Settings) -> int:
    """Backstop for webhook delivery failures (Commit 7).

    Lists completed LiveKit egresses, finds ones that don't have an
    AVAILABLE-state MeetingRecording, and calls handle_egress_completion
    to fill them in. Scheduled to run every 5 minutes — overlapping
    runs are safe because handle_egress_completion is idempotent.

    Returns the number of rows it actually MOVED to AVAILABLE/FAILED
    on this tick (for observability). Rows already in a terminal state
    are skipped here so the metric reflects real work, not no-ops.
    """
    try:
        from app.meetings import livekit_egress
        items = await livekit_egress.list_completed_egresses(settings)
    except Exception as exc:
        logger.warning(
            "meeting.reconcile_egresses.list_failed err=%s", str(exc)[:200],
        )
        return 0

    updated = 0
    for item in items:
        completion = livekit_egress.extract_egress_completion(
            type("EvtShim", (), {
                "event": "egress_ended",
                "egress_info": item,
            })()
        )
        if not completion:
            continue
        # Pre-check: skip rows already in a terminal state so this
        # counter measures actual reconciliation work (not no-ops the
        # webhook already handled). handle_egress_completion is still
        # idempotent if we did call it — this is just for the metric.
        existing = await db.execute(
            select(MeetingRecording).where(
                MeetingRecording.egress_id == completion["egress_id"],
            )
        )
        existing_rec = existing.scalar_one_or_none()
        if existing_rec is None:
            continue  # orphan — meeting deleted before egress finished
        if existing_rec.status in (
            RecordingStatus.AVAILABLE, RecordingStatus.FAILED,
        ):
            continue  # webhook already completed this row
        rec = await handle_egress_completion(
            db,
            egress_id=completion["egress_id"],
            storage_path=completion.get("storage_path"),
            duration_seconds=completion.get("duration_seconds"),
            file_size=completion.get("file_size"),
            status=completion["status"],
            settings=settings,
        )
        if rec is not None and rec.status == RecordingStatus.AVAILABLE:
            updated += 1
    return updated
