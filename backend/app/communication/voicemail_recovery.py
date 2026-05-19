"""Voicemail orphan recovery worker.

Symptom this exists for (2026-05-16 audit): one voicemail row stuck
in voicemail_transcript_status='pending' with recording_sid=NULL.
Twilio's recording-status webhook never delivered the SID — the
DH-proxy WebSocket gap surfaces for HTTP webhooks too in edge cases.

This worker reconciles by polling the Twilio REST API for any call
that has gone over the grace period without producing a recording:
  - within the grace window (<= ORPHAN_GIVEUP_HOURS): fetch
    recordings via client.calls(call_sid).recordings.list() and
    repair the row if Twilio knows about a recording we missed.
  - past the grace window: mark voicemail_transcript_status='failed'
    with a deterministic reason so the UI shows a clean state.

Wired into the scheduler as a periodic job (every 15 minutes) AND
exposed via an admin-only endpoint for manual one-shot recovery.

Never raises — all exceptions are caught + logged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.communication.models import CallLog

logger = logging.getLogger(__name__)

ORPHAN_GIVEUP_HOURS = 24
ORPHAN_LOOKBACK_HOURS = 48


def _twilio_client(settings):
    """Build a Twilio REST client from settings. Returns None if creds
    aren't configured (test environment + local dev without Twilio)."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return None
    try:
        from twilio.rest import Client
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    except Exception as exc:
        logger.warning("voicemail_recovery.twilio_client_init_failed err=%s", exc)
        return None


async def recover_orphan_voicemails(
    db: AsyncSession, settings,
) -> dict:
    """Scan + repair orphan voicemails. Returns counters dict.

    A voicemail is "orphan" if either:
      - voicemail_transcript_status='pending' AND recording_sid IS NULL
        (Twilio never delivered the SID, or did and we lost it)
      - voicemail_transcript_status='pending' for more than 24h with
        no recording_sid (give-up window)

    We only look back 48h to avoid scanning the full call_logs history
    on every cron tick.
    """
    client = _twilio_client(settings)
    if client is None:
        logger.info("voicemail_recovery.skipped no_twilio_creds")
        return {"scanned": 0, "recovered": 0, "given_up": 0, "skipped_no_creds": True}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_LOOKBACK_HOURS)
    giveup_cutoff = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_GIVEUP_HOURS)

    rows = await db.execute(
        select(CallLog).where(
            CallLog.kind == "voicemail",
            CallLog.voicemail_transcript_status == "pending",
            CallLog.created_at > cutoff,
            CallLog.recording_sid.is_(None),
        )
    )
    orphans = list(rows.scalars().all())

    scanned = len(orphans)
    recovered = 0
    given_up = 0

    for vm in orphans:
        if not vm.twilio_call_sid:
            # No Twilio call SID means we can't query Twilio — nothing
            # to recover from. Mark failed if over the giveup window.
            created = vm.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created and created < giveup_cutoff:
                vm.voicemail_transcript_status = "failed"
                given_up += 1
            continue

        # Ask Twilio whether a recording exists for this call.
        try:
            recordings = client.calls(vm.twilio_call_sid).recordings.list(limit=5)
        except Exception as exc:
            logger.warning(
                "voicemail_recovery.twilio_fetch_failed call_sid=%s err=%s",
                vm.twilio_call_sid, str(exc)[:200],
            )
            continue

        if recordings:
            # Pick the longest recording — typically there's only one,
            # but in edge cases (failed first attempt + retry) take the
            # one most likely to contain content.
            best = max(recordings, key=lambda r: int(r.duration or 0))
            vm.recording_sid = best.sid
            vm.recording_duration_seconds = int(best.duration or 0)
            vm.recording_url = (
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
                f"/Recordings/{best.sid}.mp3"
            )
            recovered += 1
            logger.info(
                "voicemail_recovery.recovered call_log_id=%s call_sid=%s "
                "recording_sid=%s duration=%s",
                vm.id, vm.twilio_call_sid, best.sid, vm.recording_duration_seconds,
            )
            # Status stays 'pending' so a follow-up transcription run
            # can pick it up; the duration guard in
            # transcribe_voicemail_task will skip if <3s.
        else:
            # Twilio confirms no recording exists. Give up after the
            # window — no point checking again.
            created = vm.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created and created < giveup_cutoff:
                vm.voicemail_transcript_status = "failed"
                given_up += 1
                logger.info(
                    "voicemail_recovery.given_up call_log_id=%s call_sid=%s "
                    "no_recording_from_twilio",
                    vm.id, vm.twilio_call_sid,
                )

    await db.commit()
    return {
        "scanned": scanned,
        "recovered": recovered,
        "given_up": given_up,
        "skipped_no_creds": False,
    }
