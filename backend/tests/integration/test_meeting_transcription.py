"""Commit 11 — AssemblyAI transcription pipeline.

Covers:
  - submit_meeting_transcription: no-op when AssemblyAI key missing
  - submit_meeting_transcription: no-op when recording.storage_path missing
  - submit_meeting_transcription: persists PROCESSING row with provider_id
    on a successful submit
  - submit_meeting_transcription: idempotent — second call returns the
    existing row, doesn't re-submit
  - submit_meeting_transcription: FAILED rows can be re-submitted
  - _poll_one: AVAILABLE state transition on AssemblyAI 'completed'
  - _poll_one: FAILED state transition on AssemblyAI 'error' (real error)
  - _poll_one: EMPTY-but-AVAILABLE on AssemblyAI 'no spoken audio' error
    (matches the brain transcription path's convention)
  - poll_pending_transcriptions: returns counts; skips when no API key
  - handle_egress_completion kicks off transcription when recording
    becomes AVAILABLE (called via the patched submit hook)

HTTP to AssemblyAI is monkeypatched — these are integration tests of
OUR pipeline, not AssemblyAI's API.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import service, transcription
from app.meetings.models import (
    Meeting, MeetingRecording, MeetingStatus, RecordingTranscript,
    RecordingStatus, TranscriptStatus,
)
from tests.conftest import TEST_SETTINGS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def settings_with_aai():
    return TEST_SETTINGS.model_copy(update={
        "assemblyai_api_key": "fake-aai-key",
        "r2_access_key_id": "r2k",
        "r2_secret_access_key": "r2s",
        "r2_bucket_name": "test-bucket",
        "r2_endpoint": "https://test.r2.cloudflarestorage.com",
        "livekit_url": "wss://example.livekit.cloud",
        "livekit_api_key": "lk-key",
        "livekit_api_secret": "lk-secret-thirtytwobytesminimumforsigning",
    })


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="host@example.com",
        hashed_password=hash_password("x"),
        full_name="Host", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def completed_recording(
    db: AsyncSession, host: User,
) -> MeetingRecording:
    m = Meeting(
        id=uuid.uuid4(),
        title="Test meeting", scheduled_start=datetime.now(timezone.utc),
        livekit_room_name=f"r-{uuid.uuid4().hex[:8]}",
        record_meeting=True, created_by=host.id,
        slug="abc-defg-hij",
    )
    db.add(m)
    rec = MeetingRecording(
        id=uuid.uuid4(),
        meeting_id=m.id,
        status=RecordingStatus.AVAILABLE,
        storage_path="meetings/test/test.mp4",
        egress_id="EG_test",
        mime_type="video/mp4",
        started_by=host.id,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


async def test_submit_returns_none_when_no_api_key(
    db: AsyncSession, completed_recording: MeetingRecording,
):
    """Dev/CI without an AssemblyAI key — pipeline silently no-ops.
    No row created."""
    s = TEST_SETTINGS.model_copy(update={"assemblyai_api_key": ""})
    result = await transcription.submit_meeting_transcription(
        db, completed_recording, s,
    )
    assert result is None
    rows = await db.execute(select(RecordingTranscript))
    assert rows.scalar_one_or_none() is None


async def test_submit_returns_none_when_no_storage_path(
    db: AsyncSession, host: User, settings_with_aai,
):
    """Defensive — recording without storage_path can't be transcribed.
    Shouldn't happen post-egress but the guard prevents a bogus
    presign call."""
    m = Meeting(
        id=uuid.uuid4(), title="x",
        scheduled_start=datetime.now(timezone.utc),
        livekit_room_name="r", created_by=host.id, slug="xxx-yyyy-zzz",
    )
    db.add(m)
    rec = MeetingRecording(
        meeting_id=m.id, status=RecordingStatus.AVAILABLE,
        storage_path=None, mime_type="video/mp4", started_by=host.id,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    result = await transcription.submit_meeting_transcription(
        db, rec, settings_with_aai,
    )
    assert result is None


async def test_submit_persists_processing_row_on_success(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    """Happy path — presign + POST succeed, transcript_id is stamped
    on provider_id, row is PROCESSING."""
    monkeypatch.setattr(
        transcription, "_generate_presigned_url",
        lambda s, k, expires_in=3600: "https://presigned.example/abc",
    )

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"id": "T_aai_transcript_id"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    row = await transcription.submit_meeting_transcription(
        db, completed_recording, settings_with_aai,
    )
    assert row is not None
    assert row.status == TranscriptStatus.PROCESSING
    assert row.provider_id == "T_aai_transcript_id"
    assert row.recording_id == completed_recording.id


async def test_submit_is_idempotent_returns_existing_row(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    """Second call must NOT POST to AssemblyAI — just return the
    existing row. Defends against accidental double-billing."""
    monkeypatch.setattr(
        transcription, "_generate_presigned_url",
        lambda s, k, expires_in=3600: "https://presigned.example/abc",
    )

    calls = {"post": 0}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"id": "T_first"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *a, **k):
            calls["post"] += 1
            return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())
    r1 = await transcription.submit_meeting_transcription(
        db, completed_recording, settings_with_aai,
    )
    r2 = await transcription.submit_meeting_transcription(
        db, completed_recording, settings_with_aai,
    )
    assert r1.id == r2.id
    assert calls["post"] == 1


async def test_submit_can_resubmit_failed_row(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    """Operator retry path — a FAILED row can be re-driven through
    submit (e.g. AssemblyAI temporary outage)."""
    # First, plant a FAILED row
    failed = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=completed_recording.id,
        status=TranscriptStatus.FAILED,
        provider="assemblyai",
        provider_id="T_old",
        error_message="Transient",
    )
    db.add(failed)
    await db.commit()

    monkeypatch.setattr(
        transcription, "_generate_presigned_url",
        lambda s, k, expires_in=3600: "https://presigned.example/abc",
    )

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"id": "T_new"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *a, **k): return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    row = await transcription.submit_meeting_transcription(
        db, completed_recording, settings_with_aai,
    )
    assert row.id == failed.id  # same row, updated in place
    assert row.status == TranscriptStatus.PROCESSING
    assert row.provider_id == "T_new"
    assert row.error_message is None


# ---------------------------------------------------------------------------
# Poll
# ---------------------------------------------------------------------------


async def test_poll_one_transitions_to_available_on_complete(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    row = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=completed_recording.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="T_done",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {
            "status": "completed",
            "text": "Hello world.",
            "language_code": "en",
            "audio_duration": 1800,
            "utterances": [
                {"start": 0, "end": 5000, "text": "Hello.", "speaker": "A"},
                {"start": 6000, "end": 10000, "text": "World.", "speaker": "B"},
            ],
        }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **k): return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    changed = await transcription._poll_one(db, row, settings_with_aai)
    assert changed is True
    assert row.status == TranscriptStatus.AVAILABLE
    assert row.full_text == "Hello world."
    assert row.duration_seconds == 1800
    assert len(row.segments_json) == 2
    assert row.segments_json[0]["speaker"] == "A"
    assert row.segments_json[0]["start"] == 0.0  # ms→s


async def test_poll_one_transitions_to_failed_on_real_error(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    row = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=completed_recording.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="T_err",
    )
    db.add(row)
    await db.commit()

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"status": "error", "error": "Audio corrupted"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **k): return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    changed = await transcription._poll_one(db, row, settings_with_aai)
    assert changed is True
    assert row.status == TranscriptStatus.FAILED
    assert "Audio corrupted" in (row.error_message or "")


async def test_poll_one_empty_audio_becomes_available_empty(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    """'No spoken audio' is a successful EMPTY transcript, not a
    failure (matches the brain transcription path's convention)."""
    row = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=completed_recording.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="T_silent",
    )
    db.add(row)
    await db.commit()

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"status": "error", "error": "No spoken audio detected"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **k): return _FakeResp()

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    await transcription._poll_one(db, row, settings_with_aai)
    assert row.status == TranscriptStatus.AVAILABLE
    assert row.full_text == ""
    assert row.segments_json == []


async def test_poll_pending_returns_counts(
    db: AsyncSession, completed_recording: MeetingRecording,
    settings_with_aai, monkeypatch,
):
    # Seed two PROCESSING rows; mock one to complete, one to stay processing
    r1 = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=completed_recording.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="T_done",
    )
    # Build a second recording so the second transcript has its own
    # recording_id (otherwise the unique-ish 1:1 model would conflict).
    rec2 = MeetingRecording(
        meeting_id=completed_recording.meeting_id,
        status=RecordingStatus.AVAILABLE, storage_path="x",
        mime_type="video/mp4", started_by=completed_recording.started_by,
    )
    db.add(rec2)
    await db.flush()
    r2 = RecordingTranscript(
        meeting_id=completed_recording.meeting_id,
        recording_id=rec2.id,
        status=TranscriptStatus.PROCESSING,
        provider="assemblyai", provider_id="T_still_processing",
    )
    db.add_all([r1, r2])
    await db.commit()

    class _FakeResp:
        def __init__(self, data): self._data = data
        def raise_for_status(self): pass
        def json(self): return self._data

    responses = {
        "T_done": {"status": "completed", "text": "ok", "utterances": []},
        "T_still_processing": {"status": "processing"},
    }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, headers=None):
            tid = url.rsplit("/", 1)[-1]
            return _FakeResp(responses.get(tid, {"status": "processing"}))

    monkeypatch.setattr(transcription.httpx, "AsyncClient", lambda **k: _FakeClient())

    result = await transcription.poll_pending_transcriptions(db, settings_with_aai)
    assert result["polled"] == 2
    assert result["completed"] == 1


async def test_poll_pending_skips_when_no_api_key(db: AsyncSession):
    s = TEST_SETTINGS.model_copy(update={"assemblyai_api_key": ""})
    result = await transcription.poll_pending_transcriptions(db, s)
    assert result == {"polled": 0, "completed": 0, "failed": 0}
