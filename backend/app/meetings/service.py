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
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.meetings.models import (
    Meeting,
    MeetingParticipant,
    MeetingRecording,
    MeetingStatus,
    ParticipantRole,
    RecordingStatus,
)
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
    from livekit.api import LiveKitAPI

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


async def create_meeting(
    db: AsyncSession,
    user: User,
    data: MeetingCreate,
    settings: Settings,
) -> Meeting:
    """Create a new meeting with host participant and optional guest invites."""
    room_name = f"meeting-{uuid.uuid4().hex[:16]}"

    meeting = Meeting(
        title=data.title,
        description=data.description,
        status=MeetingStatus.SCHEDULED,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        livekit_room_name=room_name,
        record_meeting=data.record_meeting,
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
    return meeting


async def list_meetings(
    db: AsyncSession,
    user_id: uuid.UUID,
    status_filter: MeetingStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Meeting], int]:
    """List meetings with optional status filter and pagination."""
    query = select(Meeting).options(
        selectinload(Meeting.participants),
    )

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

    lk_api = _get_livekit_api(settings)

    # Create the LiveKit room
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

    # Update meeting status
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
) -> list[MeetingRecording]:
    """List recordings with optional meeting or contact filter."""
    query = select(MeetingRecording)

    if meeting_id is not None:
        query = query.where(MeetingRecording.meeting_id == meeting_id)

    if contact_id is not None:
        # Join through Meeting to filter by contact
        query = query.join(Meeting, MeetingRecording.meeting_id == Meeting.id).where(
            Meeting.contact_id == contact_id
        )

    query = query.order_by(MeetingRecording.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def list_recordings_by_contact(
    db: AsyncSession,
    user_id: uuid.UUID,
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
        .group_by(Meeting.contact_id)
        .order_by(func.count(MeetingRecording.id).desc())
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
            .order_by(MeetingRecording.created_at.desc())
        )
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
