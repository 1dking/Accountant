"""Voicemail orphan recovery worker — when Twilio's recording-status
webhook silently drops the recording_sid, the cron worker fetches
the recording from Twilio's REST API and repairs the row.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.communication.models import CallLog
from app.communication.voicemail_recovery import (
    ORPHAN_GIVEUP_HOURS,
    recover_orphan_voicemails,
)


# ---------------------------------------------------------------------------
# Test doubles for the Twilio REST client.
# ---------------------------------------------------------------------------


class _FakeRecording:
    def __init__(self, sid: str, duration: int):
        self.sid = sid
        self.duration = duration


class _FakeRecordings:
    def __init__(self, recordings):
        self._recordings = recordings

    def list(self, limit: int = 5):
        return self._recordings[:limit]


class _FakeCallContext:
    def __init__(self, recordings):
        self.recordings = _FakeRecordings(recordings)


class _FakeTwilioClient:
    def __init__(self, recordings_by_call_sid):
        self._map = recordings_by_call_sid

    def calls(self, call_sid: str):
        return _FakeCallContext(self._map.get(call_sid, []))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeSettings:
    twilio_account_sid = "AC_test"
    twilio_auth_token = "token_test"


@pytest_asyncio.fixture
async def orphan_voicemail(db: AsyncSession, admin_user: User) -> CallLog:
    """A pending voicemail with twilio_call_sid set but recording_sid
    NULL — the exact state the audit found 1 voicemail stuck in."""
    call = CallLog(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        contact_id=None,
        direction="inbound",
        kind="voicemail",
        from_number="+12895550199",
        to_number="+13659092096",
        status="no-answer",
        twilio_call_sid="CA_orphan_test",
        recording_sid=None,
        recording_url=None,
        recording_duration_seconds=None,
        voicemail_transcript_status="pending",
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)
    return call


@pytest.mark.high
async def test_recover_orphan_voicemail_fetches_from_twilio(
    db: AsyncSession,
    orphan_voicemail: CallLog,
    monkeypatch,
):
    """Twilio knows about a recording the webhook never delivered.
    The recovery worker fetches it and patches the row."""
    # Stub the Twilio client builder so the worker uses our fake.
    fake_client = _FakeTwilioClient({
        "CA_orphan_test": [_FakeRecording(sid="RE_recovered_123", duration=8)],
    })
    monkeypatch.setattr(
        "app.communication.voicemail_recovery._twilio_client",
        lambda _settings: fake_client,
    )

    result = await recover_orphan_voicemails(db, _FakeSettings())

    assert result == {
        "scanned": 1, "recovered": 1, "given_up": 0, "skipped_no_creds": False,
    }

    await db.refresh(orphan_voicemail)
    assert orphan_voicemail.recording_sid == "RE_recovered_123"
    assert orphan_voicemail.recording_duration_seconds == 8
    # Status stays 'pending' so the transcription task can pick it up
    # on its next pass (the duration guard from Fix 1 will skip if <3s).
    assert orphan_voicemail.voicemail_transcript_status == "pending"


@pytest.mark.normal
async def test_recover_gives_up_after_24h_with_no_recording(
    db: AsyncSession,
    orphan_voicemail: CallLog,
    monkeypatch,
):
    """When Twilio confirms no recording exists AND the voicemail is
    over 24h old, mark it 'failed' so the UI shows a clean state
    instead of an indefinite spinner."""
    # Backdate the voicemail past the giveup window.
    orphan_voicemail.created_at = (
        datetime.now(timezone.utc) - timedelta(hours=ORPHAN_GIVEUP_HOURS + 1)
    )
    await db.commit()

    fake_client = _FakeTwilioClient({"CA_orphan_test": []})  # no recordings
    monkeypatch.setattr(
        "app.communication.voicemail_recovery._twilio_client",
        lambda _settings: fake_client,
    )

    result = await recover_orphan_voicemails(db, _FakeSettings())

    assert result["given_up"] == 1
    assert result["recovered"] == 0

    await db.refresh(orphan_voicemail)
    assert orphan_voicemail.voicemail_transcript_status == "failed"
