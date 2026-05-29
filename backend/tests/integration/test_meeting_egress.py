"""LiveKit Egress integration — server-side meeting recording (Commit 7).

Covers the four pieces of the new path:
  1. Auto-start: start_meeting on a record_meeting=True meeting kicks
     off Egress and writes a RECORDING-state row with egress_id set.
  2. Auto-stop: end_meeting calls stop_egress and transitions the row
     to PROCESSING.
  3. Webhook: egress_ended payload (signature-verified) moves the row
     to AVAILABLE with storage_path + duration + size, idempotently.
  4. Reconciliation: backstop job lists completed egresses and fills
     in rows the webhook missed.

External calls (LiveKit API) are stubbed via monkeypatch on the
livekit_egress module. The webhook receiver's HMAC-verify path is
exercised through a patched verify_webhook so the test doesn't need a
real LiveKit signing key.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import ValidationError
from app.meetings import livekit_egress, service
from app.meetings.models import (
    Meeting,
    MeetingRecording,
    MeetingStatus,
    RecordingStatus,
)
from tests.conftest import TEST_SETTINGS, auth_header


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def recording_meeting(db: AsyncSession, admin_user: User) -> Meeting:
    """SCHEDULED meeting with record_meeting=True so start_meeting will
    auto-kick off Egress."""
    m = Meeting(
        id=uuid.uuid4(),
        title="AI summary test",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"meeting-{uuid.uuid4().hex[:12]}",
        record_meeting=True,
        created_by=admin_user.id,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def settings_with_lk():
    """Settings with LiveKit + R2 credentials populated. start_meeting
    won't call the real LiveKit unless we monkeypatch it (we do)."""
    s = TEST_SETTINGS.model_copy(update={
        "livekit_url": "wss://example.livekit.cloud",
        "livekit_api_key": "lk-test-key",
        "livekit_api_secret": "lk-test-secret",
        "r2_access_key_id": "r2-key",
        "r2_secret_access_key": "r2-secret",
        "r2_bucket_name": "test-recordings",
        "r2_endpoint": "https://test.r2.cloudflarestorage.com",
    })
    return s


@pytest.fixture
def stub_egress(monkeypatch):
    """Stub the four LiveKit Egress entry points so tests can run
    without a real LiveKit project. Records the calls into the
    returned dict for assertion."""
    calls = {"start": [], "stop": [], "list_completed": []}

    async def fake_start(room_name, settings, **kw):
        calls["start"].append({"room": room_name, "filename": kw.get("output_filename")})
        return ("EG_test_egress_id", f"meetings/{room_name}/{room_name}.mp4")

    async def fake_stop(egress_id, settings):
        calls["stop"].append(egress_id)

    async def fake_list_completed(settings):
        return calls.get("_list_completed_return", [])

    # Patch on the imported reference INSIDE service.py via the module
    # attribute on livekit_egress — that's where the real calls happen.
    monkeypatch.setattr(livekit_egress, "start_room_recording", fake_start)
    monkeypatch.setattr(livekit_egress, "stop_room_recording", fake_stop)
    monkeypatch.setattr(livekit_egress, "list_completed_egresses", fake_list_completed)
    return calls


# ---------------------------------------------------------------------------
# 1. Auto-start on start_meeting
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_start_meeting_creates_recording_row_in_recording_state(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """start_meeting on a record_meeting=True meeting should kick off
    Egress and persist a Recording row in RECORDING state with the
    returned egress_id + storage_path. Replaces the fragile client
    MediaRecorder path."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )

    assert len(stub_egress["start"]) == 1
    assert stub_egress["start"][0]["room"] == recording_meeting.livekit_room_name

    rows = await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.meeting_id == recording_meeting.id,
        )
    )
    rec = rows.scalar_one()
    assert rec.status == RecordingStatus.RECORDING
    assert rec.egress_id == "EG_test_egress_id"
    assert rec.storage_path and "meetings/" in rec.storage_path
    assert rec.mime_type == "video/mp4"


@pytest.mark.normal
async def test_start_meeting_without_record_flag_skips_egress(
    db: AsyncSession, admin_user: User, settings_with_lk, stub_egress,
):
    """Meetings with record_meeting=False (the default) must NOT kick
    off Egress — saves $0.18/meeting + storage."""
    m = Meeting(
        id=uuid.uuid4(),
        title="Untracked sync",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"meeting-{uuid.uuid4().hex[:12]}",
        record_meeting=False,
        created_by=admin_user.id,
    )
    db.add(m)
    await db.commit()

    await service.start_meeting(db, m.id, admin_user, settings_with_lk)

    assert stub_egress["start"] == []
    rows = await db.execute(
        select(MeetingRecording).where(MeetingRecording.meeting_id == m.id)
    )
    assert rows.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# 2. Auto-stop on end_meeting
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_end_meeting_stops_egress_and_marks_processing(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """end_meeting must call stop_egress for every RECORDING-state row
    and transition them to PROCESSING. The webhook (or reconciliation)
    later moves them to AVAILABLE."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )
    await service.end_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )

    assert stub_egress["stop"] == ["EG_test_egress_id"]

    rows = await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.meeting_id == recording_meeting.id,
        )
    )
    rec = rows.scalar_one()
    assert rec.status == RecordingStatus.PROCESSING


# ---------------------------------------------------------------------------
# 3. Webhook handler
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_extract_egress_completion_pulls_full_metadata(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """The webhook handler's read path: a complete egress_ended event
    must yield egress_id + storage_path + duration + size + status.
    Walks the LiveKit EgressInfo proto shape via getattr so SDK shape
    drift doesn't break us silently."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )

    class _StubEvent:
        event = "egress_ended"
        class _Info:
            egress_id = "EG_test_egress_id"
            status = "EGRESS_COMPLETE"
            file_results = [type("FR", (), {
                "filename": "meetings/abc/abc.mp4",
                "size": 12_345_678,
                "duration": 2_700_000_000_000,  # 2700s in ns
            })()]
        egress_info = _Info()

    completion = livekit_egress.extract_egress_completion(_StubEvent())
    assert completion is not None
    assert completion["egress_id"] == "EG_test_egress_id"
    assert completion["status"] == "complete"
    assert completion["storage_path"] == "meetings/abc/abc.mp4"
    assert completion["file_size"] == 12_345_678
    assert completion["duration_seconds"] == 2700

    # Now drive the handler the same way the router would.
    rec = await service.handle_egress_completion(
        db,
        egress_id=completion["egress_id"],
        storage_path=completion["storage_path"],
        duration_seconds=completion["duration_seconds"],
        file_size=completion["file_size"],
        status=completion["status"],
    )
    assert rec is not None
    assert rec.status == RecordingStatus.AVAILABLE
    assert rec.storage_path == "meetings/abc/abc.mp4"
    assert rec.file_size == 12_345_678
    assert rec.duration_seconds == 2700


@pytest.mark.high
async def test_verify_webhook_rejects_missing_or_unsigned_payload(
    settings_with_lk,
):
    """verify_webhook is the gate the router uses — missing Auth
    header must raise ValidationError, which the router maps to 401.
    Defense against forged completion events."""
    # No header at all → reject
    with pytest.raises(ValidationError):
        livekit_egress.verify_webhook(b"{}", None, settings_with_lk)

    # Empty header → reject
    with pytest.raises(ValidationError):
        livekit_egress.verify_webhook(b"{}", "", settings_with_lk)

    # Garbage signature → reject (HMAC mismatch)
    with pytest.raises(ValidationError):
        livekit_egress.verify_webhook(
            b'{"event": "egress_ended"}',
            "Bearer not-a-real-jwt",
            settings_with_lk,
        )


@pytest.mark.high
async def test_extract_egress_completion_skips_non_terminal_events(
    settings_with_lk,
):
    """Non-completion events (egress_started, room_started, in-progress
    egress_updated) must NOT trigger handle_egress_completion. Otherwise
    the recording row would flip to AVAILABLE before the upload finished."""
    class _Started:
        event = "egress_started"
        egress_info = type("Info", (), {
            "egress_id": "EG_x",
            "status": "EGRESS_ACTIVE",
            "file_results": [],
        })()
    assert livekit_egress.extract_egress_completion(_Started()) is None

    class _RoomStarted:
        event = "room_started"
        egress_info = None
    assert livekit_egress.extract_egress_completion(_RoomStarted()) is None

    class _InFlight:
        event = "egress_updated"
        egress_info = type("Info", (), {
            "egress_id": "EG_y",
            "status": "EGRESS_ACTIVE",
            "file_results": [],
        })()
    assert livekit_egress.extract_egress_completion(_InFlight()) is None


@pytest.mark.high
async def test_webhook_is_idempotent(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """LiveKit retries on 5xx — delivering the SAME egress_ended
    twice must not double-update the row or duplicate it."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )

    # First completion → row becomes AVAILABLE
    rec1 = await service.handle_egress_completion(
        db,
        egress_id="EG_test_egress_id",
        storage_path="meetings/x/x.mp4",
        duration_seconds=1800,
        file_size=8_000_000,
        status="complete",
    )
    assert rec1 is not None
    assert rec1.status == RecordingStatus.AVAILABLE

    # Replay — second call is a no-op (idempotent)
    rec2 = await service.handle_egress_completion(
        db,
        egress_id="EG_test_egress_id",
        storage_path="meetings/x/x.mp4",
        duration_seconds=1800,
        file_size=8_000_000,
        status="complete",
    )
    assert rec2 is not None
    assert rec2.id == rec1.id  # same row

    # No duplicate rows
    count = (await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.meeting_id == recording_meeting.id,
        )
    )).scalars().all()
    assert len(count) == 1


# ---------------------------------------------------------------------------
# 4. Reconciliation job
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_reconcile_finds_orphan_completed_egress(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """When the webhook failed to deliver (network blip, backend down),
    reconcile_egresses should list completed egresses, find one whose
    Recording row is still RECORDING/PROCESSING, and complete it."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )

    # Inject a fake "completed egress" into the list response — same
    # egress_id as our started row, so reconciliation matches it.
    fake_completed = type("EgressItem", (), {
        "egress_id": "EG_test_egress_id",
        "status": "EGRESS_COMPLETE",
        "file_results": [type("FR", (), {
            "filename": "meetings/recon/recon.mp4",
            "size": 5_000_000,
            "duration": 900_000_000_000,  # 900s = 15 min
        })()],
    })()
    stub_egress["_list_completed_return"] = [fake_completed]

    updated = await service.reconcile_egresses(db, settings_with_lk)
    assert updated == 1

    rows = await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.meeting_id == recording_meeting.id,
        )
    )
    rec = rows.scalar_one()
    assert rec.status == RecordingStatus.AVAILABLE
    assert rec.storage_path == "meetings/recon/recon.mp4"
    assert rec.duration_seconds == 900


@pytest.mark.normal
async def test_reconcile_skips_already_available_recordings(
    db: AsyncSession, admin_user: User, recording_meeting: Meeting,
    settings_with_lk, stub_egress,
):
    """Reconciliation must be safe to run alongside the webhook — rows
    already in AVAILABLE state should be no-op'd (updated count = 0)."""
    await service.start_meeting(
        db, recording_meeting.id, admin_user, settings_with_lk,
    )
    # Pre-complete the row (simulates the webhook landing first)
    await service.handle_egress_completion(
        db,
        egress_id="EG_test_egress_id",
        storage_path="meetings/a/a.mp4",
        duration_seconds=600,
        file_size=3_000_000,
        status="complete",
    )

    fake_completed = type("EgressItem", (), {
        "egress_id": "EG_test_egress_id",
        "status": "EGRESS_COMPLETE",
        "file_results": [type("FR", (), {
            "filename": "meetings/a/a.mp4",
            "size": 3_000_000,
            "duration": 600_000_000_000,
        })()],
    })()
    stub_egress["_list_completed_return"] = [fake_completed]

    updated = await service.reconcile_egresses(db, settings_with_lk)
    assert updated == 0


# ---------------------------------------------------------------------------
# 5. Backwards compatibility — client-uploaded webm still works
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_existing_client_webm_recordings_still_supported(
    db: AsyncSession, admin_user: User,
):
    """Old client-uploaded recordings carry mime_type=video/webm and
    no egress_id — they must remain listable and downloadable. Pre-
    Commit-7 recordings can't get a forced migration."""
    m = Meeting(
        id=uuid.uuid4(),
        title="Legacy meeting",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"meeting-{uuid.uuid4().hex[:12]}",
        status=MeetingStatus.COMPLETED,
        record_meeting=False,
        created_by=admin_user.id,
    )
    db.add(m)
    await db.commit()

    legacy = MeetingRecording(
        meeting_id=m.id,
        status=RecordingStatus.AVAILABLE,
        storage_path="documents/legacy/abc.webm",
        mime_type="video/webm",
        file_size=4_500_000,
        duration_seconds=1200,
        started_by=admin_user.id,
        # No egress_id — distinguishes from server-recorded ones
        egress_id=None,
    )
    db.add(legacy)
    await db.commit()

    rows = await service.list_recordings(db, meeting_id=m.id, user=admin_user)
    assert len(rows) == 1
    assert rows[0].mime_type == "video/webm"
    assert rows[0].egress_id is None
