"""LiveKit Egress integration — server-side meeting recording (Commit 7).

Replaces the fragile client-side MediaRecorder path with LiveKit's
RoomCompositeEgress, which records the entire room (all participants,
all tracks) on the SFU side and uploads the MP4 directly to Cloudflare
R2 via S3-compatible API. Reliable across client disconnects, mobile
backgrounding, and tab closes.

Public surface:
  - start_room_recording(room_name, settings, output_filename=None)
      → egress_id, output_path  (called by service.start_meeting when
                                  meeting.record_meeting=True)
  - stop_room_recording(egress_id, settings)
      → None  (called by service.end_meeting)
  - list_active_egresses(room_name, settings)
      → list[EgressInfo]  (for reconciliation job)
  - list_completed_egresses(settings)
      → list[EgressInfo]  (reconciliation backstop — finds completed
                          recordings we missed via webhook loss)
  - verify_webhook(raw_body, auth_header, settings) → WebhookEvent
      raises ValidationError on HMAC failure.

Backend remains the source of truth for meeting/recording state — the
Egress API only handles recording mechanics. The webhook + reconciliation
job both call back into service.handle_egress_completed.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _require_egress_config(settings: Settings) -> None:
    """All four LiveKit + R2 settings must be set or egress can't run."""
    missing = []
    if not settings.livekit_url:
        missing.append("LIVEKIT_URL")
    if not settings.livekit_api_key:
        missing.append("LIVEKIT_API_KEY")
    if not settings.livekit_api_secret:
        missing.append("LIVEKIT_API_SECRET")
    if not settings.r2_bucket_name or not settings.r2_endpoint:
        missing.append("R2_BUCKET_NAME / R2_ENDPOINT")
    if not settings.r2_access_key_id or not settings.r2_secret_access_key:
        missing.append("R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY")
    if missing:
        raise ValidationError(
            "LiveKit Egress is not configured. Missing: " + ", ".join(missing)
        )


def _get_lkapi(settings: Settings):
    """Lazy LiveKit API client. Caller is responsible for awaiting aclose()
    when done. Wrapped in try/except so the rest of the module fails loudly
    if livekit-api isn't installed (instead of silently no-oping)."""
    try:
        from livekit.api import LiveKitAPI
    except ModuleNotFoundError as exc:
        raise ValidationError("LiveKit SDK is not installed.") from exc
    return LiveKitAPI(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )


def _build_s3_upload(settings: Settings):
    """S3Upload payload pointing at Cloudflare R2. R2 is S3-compatible —
    LiveKit's Egress just sees an S3 endpoint with a custom URL."""
    from livekit.api import S3Upload
    return S3Upload(
        access_key=settings.r2_access_key_id,
        secret=settings.r2_secret_access_key,
        bucket=settings.r2_bucket_name,
        endpoint=settings.r2_endpoint,
        region="auto",
        force_path_style=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_room_recording(
    room_name: str,
    settings: Settings,
    *,
    output_filename: str | None = None,
) -> tuple[str, str]:
    """Start a RoomCompositeEgress writing MP4 to R2.

    Returns (egress_id, output_path). output_path is the R2 key — that's
    what we persist on MeetingRecording.storage_path so download/stream
    endpoints can resolve it later.

    The composite layout is "speaker" (focus on dominant speaker, others
    in a strip) — Granola/Otter style default. Users can swap to grid
    later via update_layout if we ship a control. The default audio mixer
    captures every participant's microphone.
    """
    _require_egress_config(settings)
    # Path within the bucket — predictable per-meeting-room layout makes
    # debugging / orphan-detection straightforward.
    output_path = output_filename or f"meetings/{room_name}/{room_name}.mp4"

    from livekit.api import (
        EncodedFileOutput,
        EncodedFileType,
        RoomCompositeEgressRequest,
    )

    req = RoomCompositeEgressRequest(
        room_name=room_name,
        layout="speaker",
        audio_only=False,
        video_only=False,
        file_outputs=[
            EncodedFileOutput(
                file_type=EncodedFileType.MP4,
                filepath=output_path,
                s3=_build_s3_upload(settings),
            )
        ],
    )

    api = _get_lkapi(settings)
    try:
        info = await api.egress.start_room_composite_egress(req)
    finally:
        await api.aclose()
    logger.info(
        "livekit.egress_started room=%s egress_id=%s output=%s",
        room_name, info.egress_id, output_path,
    )
    return info.egress_id, output_path


async def stop_room_recording(egress_id: str, settings: Settings) -> None:
    """Stop an active egress. Idempotent — stopping an already-stopped
    egress raises a LiveKit twirp error which we swallow (logged at
    warning)."""
    _require_egress_config(settings)
    from livekit.api import StopEgressRequest

    api = _get_lkapi(settings)
    try:
        await api.egress.stop_egress(StopEgressRequest(egress_id=egress_id))
        logger.info("livekit.egress_stopped egress_id=%s", egress_id)
    except Exception as exc:  # twirp error / already-stopped
        logger.warning(
            "livekit.egress_stop_failed egress_id=%s err=%s",
            egress_id, str(exc)[:200],
        )
    finally:
        await api.aclose()


async def list_active_egresses(
    room_name: str, settings: Settings
) -> list[Any]:
    """Return any egresses currently active for this room."""
    _require_egress_config(settings)
    from livekit.api import ListEgressRequest

    api = _get_lkapi(settings)
    try:
        resp = await api.egress.list_egress(
            ListEgressRequest(room_name=room_name, active=True)
        )
    finally:
        await api.aclose()
    return list(resp.items)


async def list_completed_egresses(settings: Settings) -> list[Any]:
    """List ALL completed egresses across rooms (last ~24h-ish per
    LiveKit's retention). Reconciliation job iterates this list, drops
    any whose egress_id we already have a row for, creates rows for
    the rest."""
    _require_egress_config(settings)
    from livekit.api import ListEgressRequest

    api = _get_lkapi(settings)
    try:
        resp = await api.egress.list_egress(ListEgressRequest(active=False))
    finally:
        await api.aclose()
    return list(resp.items)


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------


def verify_webhook(
    raw_body: bytes, auth_header: str | None, settings: Settings
) -> Any:
    """Verify the LiveKit webhook signature and return the parsed event.

    LiveKit signs webhooks with a JWT-shape token in the Authorization
    header; the TokenVerifier reconstitutes the body and verifies HMAC.
    Mismatched signature → ValidationError (router maps to 401).
    """
    if not auth_header:
        raise ValidationError("Missing Authorization header on webhook")
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise ValidationError("LiveKit credentials not configured")
    try:
        from livekit.api import TokenVerifier, WebhookReceiver
    except ModuleNotFoundError as exc:
        raise ValidationError("LiveKit SDK is not installed.") from exc

    verifier = TokenVerifier(
        settings.livekit_api_key, settings.livekit_api_secret
    )
    receiver = WebhookReceiver(verifier)
    body_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
    try:
        event = receiver.receive(body_str, auth_header)
    except Exception as exc:
        raise ValidationError(f"Webhook signature verification failed: {exc}")
    return event


def extract_egress_completion(event: Any) -> dict | None:
    """Pull the recording metadata out of a LiveKit webhook event.

    Returns None if the event isn't an egress_ended / egress_updated
    completion. Returns:
      {
        "egress_id": str,
        "storage_path": str | None,  # R2 key the file was written to
        "duration_seconds": int | None,
        "file_size": int | None,
        "status": "complete" | "failed",
      }

    Defensive against shape changes between SDK versions — we read
    attributes via getattr with defaults rather than dotted access.
    """
    # event.event is the string event name; event.egress_info carries
    # the EgressInfo proto. Both .egress_updated and .egress_ended carry
    # file metadata once recording finishes.
    event_name = getattr(event, "event", "")
    if event_name not in ("egress_ended", "egress_updated"):
        return None
    info = getattr(event, "egress_info", None)
    if info is None:
        return None

    egress_id = getattr(info, "egress_id", None)
    if not egress_id:
        return None

    status_raw = getattr(info, "status", None)
    # Egress status enum values include EGRESS_COMPLETE / EGRESS_FAILED /
    # EGRESS_ABORTED. We treat anything that isn't terminal as "still in
    # progress" and bail.
    status_name = str(status_raw) if status_raw is not None else ""
    if "COMPLETE" in status_name:
        status = "complete"
    elif "FAILED" in status_name or "ABORTED" in status_name:
        status = "failed"
    else:
        return None  # not terminal yet

    # Pull the first file output's metadata. EgressInfo.file_results
    # (newer SDK) or file (older) carries filename + duration + size.
    storage_path: str | None = None
    duration_seconds: int | None = None
    file_size: int | None = None

    file_results = getattr(info, "file_results", None) or []
    if file_results:
        fr = file_results[0]
        storage_path = getattr(fr, "filename", None) or getattr(fr, "location", None)
        size = getattr(fr, "size", None)
        if size:
            file_size = int(size)
        dur_ms = getattr(fr, "duration", None)
        if dur_ms:
            # LiveKit reports duration in nanoseconds (per proto)
            duration_seconds = int(int(dur_ms) / 1_000_000_000)

    return {
        "egress_id": egress_id,
        "storage_path": storage_path,
        "duration_seconds": duration_seconds,
        "file_size": file_size,
        "status": status,
    }
