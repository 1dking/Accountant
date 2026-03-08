
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


async def _scan_gmail_accounts() -> None:
    """Job: scan connected Gmail accounts for new emails."""
    try:
        async with _session_factory() as db:
            from app.integrations.gmail.service import scan_all_accounts

            count = await scan_all_accounts(db, _settings)
            if count > 0:
                logger.info("Gmail scan found %d new emails", count)
    except ImportError:
        pass  # Gmail module not yet built
    except Exception:
        logger.exception("Error scanning Gmail accounts")


async def _sync_plaid_transactions() -> None:
    """Job: sync transactions from connected bank accounts."""
    try:
        async with _session_factory() as db:
            from app.integrations.plaid.service import sync_all_connections

            count = await sync_all_connections(db, _settings)
            if count > 0:
                logger.info("Plaid sync imported %d transactions", count)
    except ImportError:
        pass  # Plaid module not yet built
    except Exception:
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


def setup_scheduler(session_factory: Any, settings: Any = None) -> None:
    """Register all periodic jobs and start the scheduler."""
    global _session_factory, _settings
    _session_factory = session_factory
    _settings = settings

    scheduler.add_job(
        _process_recurring_rules,
        CronTrigger(hour=1, minute=0),
        id="process_recurring_rules",
        replace_existing=True,
    )

    scheduler.add_job(
        _check_overdue_invoices,
        CronTrigger(hour=2, minute=0),
        id="check_overdue_invoices",
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

    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
