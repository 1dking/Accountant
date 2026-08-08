
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_session_factory: Any = None
_settings: Any = None


async def _process_recurring_rules() -> None:
    """Job: process due recurring transactions."""
    try:
        async with _session_factory() as db:
            from app.recurring.service import process_recurring_rules

            result = await process_recurring_rules(db)
            if result > 0:
                logger.info("Processed %d recurring rules", result)
    except Exception:
        logger.exception("Error processing recurring rules")


async def _cleanup_old_notifications() -> None:
    """Job: delete notifications older than 30 days. Daily at 3am UTC.

    The notifications table grows fast (one row per SMS + voicemail +
    automation event), and the bell only shows the last 20 anyway.
    Keeping 30 days is the sweet spot for UX (history available if you
    look) vs storage growth.
    """
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import delete as sa_delete
        from app.notifications.models import Notification

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        async with _session_factory() as db:
            result = await db.execute(
                sa_delete(Notification).where(Notification.created_at < cutoff)
            )
            await db.commit()
            count = result.rowcount or 0
            if count > 0:
                logger.info("notifications_cleanup deleted=%d cutoff=%s", count, cutoff.isoformat())
    except Exception:
        logger.exception("Error in notifications cleanup")


async def _check_overdue_invoices() -> None:
    """Job: mark past-due invoices as overdue."""
    try:
        async with _session_factory() as db:
            from app.invoicing.service import check_overdue_invoices

            count = await check_overdue_invoices(db)
            if count > 0:
                logger.info("Marked %d invoices as overdue", count)
    except Exception:
        logger.exception("Error checking overdue invoices")


async def _snapshot_active_clients() -> None:
    """Job: OBRAIN_EVENT_SPEC.md §3 — monthly `active_client_snapshot` per
    contact-book owner, 30d + 90d windows. Feeds the Pricing Lab's
    Value-Metric Explorer (the `activeClients` candidate). Monthly, not
    interval-based, so the "as-of" moment matches the spec's "one row per
    orgId per month" shape for getValueMetrics().
    """
    try:
        async with _session_factory() as db:
            from app.events.service import snapshot_active_clients

            count = await snapshot_active_clients(db)
            if count > 0:
                logger.info("Snapshotted active clients for %d accounts", count)
    except Exception:
        logger.exception("Error snapshotting active clients")


async def _process_proposal_follow_ups() -> None:
    """Job: send follow-ups for proposals sitting unsigned past their delay."""
    try:
        async with _session_factory() as db:
            from app.proposals.service import process_pending_follow_ups

            count = await process_pending_follow_ups(db, _settings)
            if count > 0:
                logger.info("Sent %d proposal follow-ups", count)
    except Exception:
        logger.exception("Error processing proposal follow-ups")


async def _scan_gmail_accounts() -> None:
    """Job: scan connected Gmail accounts for new emails."""
    try:
        async with _session_factory() as db:
            from app.integrations.gmail.service import scan_all_accounts

            count = await scan_all_accounts(db, _settings)
            if count > 0:
                logger.info("Gmail scan found %d new emails", count)
    except Exception:
        # Deliberately no `except ImportError: pass` here. The Gmail module
        # exists now, so a broken import means a real regression — swallowing
        # it would silently stop the scan with nothing in the log.
        logger.exception("Error scanning Gmail accounts")


async def _recover_orphan_voicemails() -> None:
    """Job: poll Twilio for recordings on voicemails that webhooks
    missed. Closes the DH-proxy gap where /voicemail-status sometimes
    doesn't deliver the recording_sid. Runs every 15 minutes."""
    try:
        async with _session_factory() as db:
            from app.communication.voicemail_recovery import recover_orphan_voicemails
            result = await recover_orphan_voicemails(db, _settings)
            if result.get("recovered", 0) > 0 or result.get("given_up", 0) > 0:
                logger.info("voicemail_recovery.tick %s", result)
    except Exception:
        logger.exception("Error in voicemail orphan recovery")


async def _reconcile_meeting_egresses() -> None:
    """Job: backstop for LiveKit Egress webhook delivery failures
    (Commit 7). Lists completed egresses, fills in any MeetingRecording
    rows the webhook missed. Idempotent — safe to overlap. Runs every
    5 minutes."""
    if _settings is None:
        return
    # Cheap check before doing real work — skip the job entirely on
    # deployments that don't have LiveKit configured (dev boxes, etc).
    if not _settings.livekit_url or not _settings.livekit_api_key:
        return
    try:
        async with _session_factory() as db:
            from app.meetings.service import reconcile_egresses
            updated = await reconcile_egresses(db, _settings)
            if updated > 0:
                logger.info("meeting.reconcile_egresses.tick updated=%d", updated)
    except Exception:
        logger.exception("Error in meeting egress reconciliation")


async def _poll_meeting_transcriptions() -> None:
    """Job: poll AssemblyAI for completion on any PROCESSING transcripts
    (Commit 11). Runs every 2 minutes — AssemblyAI's nano tier finishes
    a 45-min recording in ~2-3 min, so this catches most completions
    within one tick of finishing."""
    if _settings is None or not _settings.assemblyai_api_key:
        return
    try:
        async with _session_factory() as db:
            from app.meetings.transcription import poll_pending_transcriptions
            result = await poll_pending_transcriptions(db, _settings)
            if result["polled"] > 0:
                logger.info("meeting.transcription_poll.tick %s", result)
    except Exception:
        logger.exception("Error in meeting transcription poll")


async def _drive_meeting_summaries() -> None:
    """Job: drive Claude summaries for any AVAILABLE transcripts that
    don't yet have one (Commit 12). Backstop for the inline kickoff
    in transcription._poll_one — catches summaries the inline path
    missed (Claude outage, restart mid-batch, etc.). Every 5 minutes."""
    if _settings is None or not _settings.anthropic_api_key:
        return
    try:
        async with _session_factory() as db:
            from app.meetings.summarization import drive_pending_summaries
            result = await drive_pending_summaries(db, _settings)
            if result["processed"] > 0 or result["failed"] > 0:
                logger.info("meeting.summary_drive.tick %s", result)
    except Exception:
        logger.exception("Error in meeting summary drive")


async def _drive_meeting_quote_drafts() -> None:
    """Job: backstop for the inline kickoff of quote drafts (Commit 15).
    Finds AVAILABLE summaries that don't yet have a draft and queues
    them. Every 5 minutes."""
    if _settings is None or not _settings.anthropic_api_key:
        return
    try:
        async with _session_factory() as db:
            from app.meetings.quote_draft import drive_pending_quote_drafts
            result = await drive_pending_quote_drafts(db, _settings)
            if result["processed"] > 0 or result["skipped"] > 0 or result["failed"] > 0:
                logger.info("meeting.quote_draft_drive.tick %s", result)
    except Exception:
        logger.exception("Error in meeting quote draft drive")


async def _sync_plaid_transactions() -> None:
    """Job: sync transactions from connected bank accounts."""
    try:
        async with _session_factory() as db:
            from app.integrations.plaid.service import sync_all_connections

            count = await sync_all_connections(db, _settings)
            if count > 0:
                logger.info("Plaid sync imported %d transactions", count)
    except Exception:
        # See _scan_gmail_accounts: the Plaid module exists, so an ImportError
        # here is a regression to surface, not a condition to swallow.
        logger.exception("Error syncing Plaid transactions")


async def _process_payment_reminders() -> None:
    """Job: send payment reminders based on active reminder rules."""
    try:
        async with _session_factory() as db:
            from app.invoicing.reminder_service import process_reminders

            count = await process_reminders(db, _settings)
            if count > 0:
                logger.info("Sent %d payment reminders", count)
    except Exception:
        logger.exception("Error processing payment reminders")


async def _send_booking_reminders() -> None:
    """Job: send 24h and 1h booking reminders via email."""
    try:
        async with _session_factory() as db:
            from datetime import datetime, timedelta, timezone as tz
            from app.scheduling.service import (
                get_bookings_needing_reminders,
                send_booking_reminder,
            )

            bookings = await get_bookings_needing_reminders(db)
            sent = 0
            now = datetime.now(tz.utc)
            for booking in bookings:
                start = booking.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=tz.utc)

                if not booking.reminder_1h_sent and start <= now + timedelta(hours=1):
                    if await send_booking_reminder(db, booking, "1h"):
                        sent += 1
                elif not booking.reminder_24h_sent and start <= now + timedelta(hours=24):
                    if await send_booking_reminder(db, booking, "24h"):
                        sent += 1

            if sent > 0:
                logger.info("Sent %d booking reminders", sent)
    except Exception:
        logger.exception("Error sending booking reminders")


async def _aggregate_page_analytics() -> None:
    """Job: aggregate yesterday's page visit data into daily summary table."""
    try:
        async with _session_factory() as db:
            from app.pages.service import aggregate_daily_analytics

            count = await aggregate_daily_analytics(db)
            if count > 0:
                logger.info("Aggregated analytics for %d pages", count)
    except Exception:
        logger.exception("Error aggregating page analytics")


async def _check_coaching_nudges() -> None:
    """Job: check for coaching nudge triggers (stale proposals, overdue invoices)."""
    try:
        from app.coach.service import check_coaching_nudges

        count = await check_coaching_nudges(_session_factory)
        if count > 0:
            logger.info("Created %d coaching nudges", count)
    except Exception:
        logger.exception("Error checking coaching nudges")


async def _run_monthly_reports() -> None:
    """Job: generate monthly intelligence reports for all users."""
    try:
        from app.coach.service import run_monthly_reports

        count = await run_monthly_reports(_session_factory)
        if count > 0:
            logger.info("Generated %d monthly intelligence reports", count)
    except Exception:
        logger.exception("Error running monthly reports")


async def _fetch_daily_news() -> None:
    """Job: fetch news articles for all users with news preferences."""
    try:
        from app.news.service import fetch_news_all_users

        count = await fetch_news_all_users(_session_factory)
        if count > 0:
            logger.info("Fetched %d news articles", count)
    except Exception:
        logger.exception("Error fetching daily news")


async def _sync_google_calendars() -> None:
    """Job: sync events with connected Google Calendar accounts."""
    try:
        async with _session_factory() as db:
            from app.integrations.google_calendar.service import sync_all_accounts

            count = await sync_all_accounts(db, _settings)
            if count > 0:
                logger.info("Google Calendar sync pulled %d events", count)
    except Exception:
        logger.exception("Error syncing Google Calendar")


async def _run_scheduled_workflows() -> None:
    """Job: fire workflows whose trigger is SCHEDULED and that are due."""
    try:
        async with _session_factory() as db:
            from app.workflows.service import run_scheduled_workflows

            ran = await run_scheduled_workflows(db)
            if ran:
                logger.info("Ran %d scheduled workflows", ran)
    except Exception:
        logger.exception("Error running scheduled workflows")


async def _resume_waiting_workflows() -> None:
    """Job: continue linear workflow executions parked on a WAIT_DELAY whose
    delay has now elapsed. Without this, any multi-step workflow with a delay
    stalls in WAITING forever (e.g. the Invoice Overdue Follow-Up template).
    Runs every minute."""
    try:
        async with _session_factory() as db:
            from app.workflows.service import resume_waiting_workflows

            resumed = await resume_waiting_workflows(db)
            if resumed:
                logger.info("Resumed %d waiting workflows", resumed)
    except Exception:
        logger.exception("Error resuming waiting workflows")


async def _complete_past_bookings() -> None:
    """Job: mark confirmed bookings whose end time has passed as COMPLETED.

    Nothing else ever set COMPLETED, so the APPOINTMENT_COMPLETED trigger had
    no source event — this is that source.
    """
    try:
        async with _session_factory() as db:
            from app.scheduling.service import complete_past_bookings

            done = await complete_past_bookings(db)
            if done:
                logger.info("Marked %d bookings completed", done)
    except Exception:
        logger.exception("Error completing past bookings")


async def _meter_telephony_usage() -> None:
    """Job: pull yesterday's Twilio usage per subaccount, rebill it, and record
    our actual cost alongside so realised margin is queryable."""
    try:
        async with _session_factory() as db:
            from app.billing.telephony_metering import meter_all

            result = await meter_all(db, _settings, period="yesterday")
            if result.get("tenants"):
                logger.info(
                    "telephony.metered tenants=%s billed=$%.4f cost=$%.4f margin=$%.4f",
                    result["tenants"], result["billed_usd"],
                    result["our_cost_usd"], result["margin_usd"],
                )
    except Exception:
        logger.exception("Error metering telephony usage")


async def _refresh_a2p_registrations() -> None:
    """Job: poll carrier review status for pending A2P registrations.

    Campaign review takes 10-15 days, so hourly is plenty.
    """
    try:
        async with _session_factory() as db:
            from app.communication.a2p import refresh_all_pending

            updated = await refresh_all_pending(db, _settings)
            if updated:
                logger.info("a2p.status_refreshed updated=%d", updated)
    except Exception:
        logger.exception("Error refreshing A2P registrations")


async def _prune_audit_logs() -> None:
    """Job: prune audit rows past the retention window. Daily at 3:30am UTC."""
    try:
        async with _session_factory() as db:
            from app.audit.service import prune_audit_logs

            count = await prune_audit_logs(db)
            if count > 0:
                logger.info("audit_logs pruned=%d", count)
    except Exception:
        logger.exception("Error pruning audit logs")


async def _enforce_plaid_retention() -> None:
    """Job: age out Plaid-derived transactions per plaid_data_retention_days.

    No-op when retention is disabled (the default), so this is safe to always
    register. Daily at 4:15am UTC.
    """
    if _settings is None:
        return
    try:
        async with _session_factory() as db:
            from app.privacy.service import enforce_plaid_retention

            days = int(getattr(_settings, "plaid_data_retention_days", 0) or 0)
            count = await enforce_plaid_retention(db, days)
            if count > 0:
                logger.info("plaid_retention deleted_transactions=%d cutoff_days=%d", count, days)
    except Exception:
        logger.exception("Error enforcing Plaid retention")


def setup_scheduler(session_factory: Any, settings: Any = None) -> None:
    """Register all periodic jobs and start the scheduler."""
    global _session_factory, _settings
    _session_factory = session_factory
    _settings = settings

    # Telephony rebilling: meter yesterday's usage once a day, after Twilio has
    # finalised it. Idempotent on the ledger's external_ref, so a retry or an
    # overlapping run cannot double-bill.
    scheduler.add_job(
        _meter_telephony_usage,
        CronTrigger(hour=6, minute=30),
        id="meter_telephony_usage",
        replace_existing=True,
    )

    scheduler.add_job(
        _refresh_a2p_registrations,
        IntervalTrigger(hours=1),
        id="refresh_a2p_registrations",
        replace_existing=True,
    )

    scheduler.add_job(
        _process_recurring_rules,
        CronTrigger(hour=1, minute=0),
        id="process_recurring_rules",
        replace_existing=True,
    )

    # Time-based workflow trigger. 15 minutes is the granularity the SCHEDULED
    # cron matcher buckets against — keep the two in step if this changes.
    scheduler.add_job(
        _run_scheduled_workflows,
        IntervalTrigger(minutes=15),
        id="run_scheduled_workflows",
        replace_existing=True,
    )

    # WAIT_DELAY resumption: continue linear executions parked on a delay once
    # their resume_at is past. Every minute keeps the delay's granularity tight
    # without meaningful load (only picks up rows that are actually due).
    scheduler.add_job(
        _resume_waiting_workflows,
        IntervalTrigger(minutes=1),
        id="resume_waiting_workflows",
        replace_existing=True,
    )

    scheduler.add_job(
        _complete_past_bookings,
        IntervalTrigger(minutes=15),
        id="complete_past_bookings",
        replace_existing=True,
    )

    scheduler.add_job(
        _check_overdue_invoices,
        CronTrigger(hour=2, minute=0),
        id="check_overdue_invoices",
        replace_existing=True,
    )

    scheduler.add_job(
        _snapshot_active_clients,
        CronTrigger(day=1, hour=3, minute=0),
        id="snapshot_active_clients",
        replace_existing=True,
    )

    scheduler.add_job(
        _scan_gmail_accounts,
        IntervalTrigger(minutes=30),
        id="scan_gmail_accounts",
        replace_existing=True,
    )

    scheduler.add_job(
        _sync_plaid_transactions,
        IntervalTrigger(hours=4),
        id="sync_plaid_transactions",
        replace_existing=True,
    )

    scheduler.add_job(
        _process_payment_reminders,
        CronTrigger(hour=8, minute=0),
        id="process_payment_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        _send_booking_reminders,
        IntervalTrigger(minutes=15),
        id="send_booking_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        _sync_google_calendars,
        IntervalTrigger(minutes=15),
        id="sync_google_calendars",
        replace_existing=True,
    )

    scheduler.add_job(
        _aggregate_page_analytics,
        CronTrigger(hour=3, minute=0),
        id="aggregate_page_analytics",
        replace_existing=True,
    )

    scheduler.add_job(
        _check_coaching_nudges,
        IntervalTrigger(hours=1),
        id="check_coaching_nudges",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_monthly_reports,
        CronTrigger(day=1, hour=4, minute=0),
        id="run_monthly_reports",
        replace_existing=True,
    )

    scheduler.add_job(
        _fetch_daily_news,
        CronTrigger(hour=5, minute=0),
        id="fetch_daily_news",
        replace_existing=True,
    )

    scheduler.add_job(
        _cleanup_old_notifications,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_notifications",
        replace_existing=True,
    )

    scheduler.add_job(
        _recover_orphan_voicemails,
        IntervalTrigger(minutes=15),
        id="recover_orphan_voicemails",
        replace_existing=True,
    )

    scheduler.add_job(
        _reconcile_meeting_egresses,
        IntervalTrigger(minutes=5),
        id="reconcile_meeting_egresses",
        replace_existing=True,
    )

    scheduler.add_job(
        _poll_meeting_transcriptions,
        IntervalTrigger(minutes=2),
        id="poll_meeting_transcriptions",
        replace_existing=True,
    )

    scheduler.add_job(
        _drive_meeting_summaries,
        IntervalTrigger(minutes=5),
        id="drive_meeting_summaries",
        replace_existing=True,
    )

    scheduler.add_job(
        _drive_meeting_quote_drafts,
        IntervalTrigger(minutes=5),
        id="drive_meeting_quote_drafts",
        replace_existing=True,
    )

    scheduler.add_job(
        _process_proposal_follow_ups,
        IntervalTrigger(minutes=30),
        id="process_proposal_follow_ups",
        replace_existing=True,
    )

    scheduler.add_job(
        _prune_audit_logs,
        CronTrigger(hour=3, minute=30),
        id="prune_audit_logs",
        replace_existing=True,
    )

    scheduler.add_job(
        _enforce_plaid_retention,
        CronTrigger(hour=4, minute=15),
        id="enforce_plaid_retention",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
