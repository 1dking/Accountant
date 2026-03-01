"""FastAPI router for the meetings module."""

import asyncio
import io
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.exceptions import ValidationError
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role
from app.documents.storage import LocalStorage, StorageBackend
from app.meetings import service
from app.meetings.models import MeetingRecording, MeetingStatus, RecordingStatus
from app.meetings.schemas import (
    GuestJoinRequest,
    MeetingCreate,
    MeetingListItem,
    MeetingParticipantAdd,
    MeetingParticipantResponse,
    MeetingRecordingResponse,
    MeetingResponse,
    MeetingUpdate,
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
    _: Annotated[User, Depends(get_current_user)],
    status: MeetingStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List meetings with optional status filter."""
    meetings, total_count = await service.list_meetings(
        db, user_id=_.id, status_filter=status, skip=skip, limit=limit
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
    _: Annotated[User, Depends(get_current_user)],
    meeting_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List all recordings with optional filters."""
    recordings = await service.list_recordings(
        db, meeting_id=meeting_id, contact_id=contact_id, skip=skip, limit=limit
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
    grouped = await service.list_recordings_by_contact(db, current_user.id)
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
) -> StreamingResponse:
    """Download a recording file."""
    recording = await service.get_recording_stream_info(db, recording_id, current_user)
    if not recording.storage_path:
        raise ValidationError("Recording file is not available.")

    data = await storage.read(recording.storage_path)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=recording.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="recording-{recording.id}.{recording.mime_type.split("/")[-1]}"',
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
    """Stream a recording with Range header support."""
    recording = await service.get_recording_stream_info(db, recording_id, current_user)
    if not recording.storage_path:
        raise ValidationError("Recording file is not available.")

    data = await storage.read(recording.storage_path)
    total_size = len(data)

    # Handle Range header for partial content
    range_header = request.headers.get("range")
    if range_header:
        # Parse "bytes=start-end"
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
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """List recordings for a specific meeting."""
    recordings = await service.list_recordings(db, meeting_id=meeting_id)
    return {"data": [MeetingRecordingResponse.model_validate(r) for r in recordings]}


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
# Webhook endpoint
# ---------------------------------------------------------------------------


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

    await websocket.accept()

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers={},
            max_size=None,
            open_timeout=10,
        ) as lk_ws:

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
                except Exception:
                    pass

            async def livekit_to_client():
                """Forward frames from LiveKit to browser."""
                try:
                    async for message in lk_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception:
                    pass

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_livekit()),
                    asyncio.create_task(livekit_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the remaining task
            for task in pending:
                task.cancel()

    except Exception:
        logger.debug("LiveKit proxy connection closed", exc_info=True)
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
