"""Voicemail min-duration guard — recordings under 3 seconds are
marked 'too_short' instead of being shipped to AssemblyAI.

Symptom (2026-05-16 audit): 5 of 7 voicemails were 1-2 second
recordings that all failed AssemblyAI transcription, producing
useless 'failed' status and cluttering the error logs. Fix moves the
guard to task entry so we never queue a doomed transcription call.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User
from app.communication.models import CallLog
from app.communication.voicemail import (
    MIN_TRANSCRIBE_DURATION_SECONDS,
    transcribe_voicemail_task,
)


@pytest_asyncio.fixture
async def short_voicemail(db: AsyncSession, admin_user: User) -> CallLog:
    """A pending voicemail with a 2-second recording — under the
    transcription floor. Inserted with status='pending' to mimic the
    real router flow where the status is flipped before the task fires."""
    call = CallLog(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        contact_id=None,
        direction="inbound",
        kind="voicemail",
        from_number="+12895550199",
        to_number="+13659092096",
        status="no-answer",
        recording_sid="REtest123",
        recording_url="https://api.twilio.com/dummy",
        recording_duration_seconds=2,
        voicemail_transcript_status="pending",
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)
    return call


@pytest.mark.high
async def test_voicemail_skip_transcription_under_3_seconds(
    db: AsyncSession,
    short_voicemail: CallLog,
    monkeypatch,
):
    """Recordings under MIN_TRANSCRIBE_DURATION_SECONDS get marked
    'too_short' at task entry, AssemblyAI is never called, the memory
    chain is never fired.

    We use a fail-loud stub for transcribe_with_assemblyai so any call
    into it surfaces as a test failure rather than a silent network
    attempt.
    """
    transcribe_called = {"yes": False}

    async def _explode(*_args, **_kwargs):
        transcribe_called["yes"] = True
        raise AssertionError(
            "transcribe_with_assemblyai must NOT be called for sub-3s recordings",
        )

    monkeypatch.setattr(
        "app.brain.transcription_service.transcribe_with_assemblyai",
        _explode,
    )

    # Same session_factory the engine fixture exposes, so the task's
    # own session writes are visible to our reload below.
    factory = async_sessionmaker(db.bind, expire_on_commit=False)

    # Sanity check on the constant — if someone bumps it accidentally,
    # this test should flag it.
    assert MIN_TRANSCRIBE_DURATION_SECONDS == 3

    await transcribe_voicemail_task(
        call_log_id=short_voicemail.id,
        recording_sid="REtest123",
        account_sid="AC_test",
        auth_token="token_test",
        session_factory=factory,
    )

    assert transcribe_called["yes"] is False, (
        "AssemblyAI was hit for a 2-second recording — guard didn't fire"
    )

    # Re-fetch through a fresh session to bypass the test session's
    # identity map cache of the original row.
    async with factory() as fresh:
        row = await fresh.execute(
            select(CallLog).where(CallLog.id == short_voicemail.id)
        )
        updated = row.scalar_one()
        assert updated.voicemail_transcript_status == "too_short"
        assert updated.voicemail_transcript is None
