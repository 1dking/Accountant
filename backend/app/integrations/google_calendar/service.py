
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError

from .models import GoogleCalendarAccount

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _build_flow(settings: Settings):
    """Build a google_auth_oauthlib Flow for Google Calendar."""
    from google_auth_oauthlib.flow import Flow

    redirect_uri = settings.google_calendar_redirect_uri
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=CALENDAR_SCOPES,
    )
    flow.redirect_uri = redirect_uri
    return flow


async def get_google_auth_url(user_id: uuid.UUID, settings: Settings) -> str:
    """Generate OAuth2 authorization URL for Google Calendar."""
    flow = _build_flow(settings)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(user_id),
    )
    return auth_url


async def handle_oauth_callback(
    db: AsyncSession, code: str, state: str, settings: Settings
) -> GoogleCalendarAccount:
    """Exchange authorization code for tokens, encrypt, and store."""
    from googleapiclient.discovery import build as build_service

    flow = _build_flow(settings)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    service = build_service("calendar", "v3", credentials=credentials)
    calendar_list = service.calendarList().list().execute()

    # Get the primary calendar's email
    email = ""
    for cal in calendar_list.get("items", []):
        if cal.get("primary"):
            email = cal.get("id", "")
            break

    if not email:
        # Fallback: get from userinfo
        from google.oauth2 import id_token
        from google.auth.transport import requests

        try:
            info = id_token.verify_oauth2_token(
                credentials.id_token,
                requests.Request(),
                settings.google_client_id,
            )
            email = info.get("email", "unknown@gmail.com")
        except Exception:
            email = "unknown@gmail.com"

    encryption = get_encryption_service()
    encrypted_access = encryption.encrypt(credentials.token)
    encrypted_refresh = encryption.encrypt(credentials.refresh_token or "")

    user_id = uuid.UUID(state)

    # Check if already connected
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.user_id == user_id,
        GoogleCalendarAccount.email == email,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_access_token = encrypted_access
        existing.encrypted_refresh_token = encrypted_refresh
        existing.token_expiry = credentials.expiry
        existing.scopes = " ".join(credentials.scopes or [])
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    account = GoogleCalendarAccount(
        user_id=user_id,
        email=email,
        encrypted_access_token=encrypted_access,
        encrypted_refresh_token=encrypted_refresh,
        token_expiry=credentials.expiry,
        scopes=" ".join(credentials.scopes or []),
        is_active=True,
        selected_calendar_id=email,  # Default to primary calendar
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _get_calendar_service(account: GoogleCalendarAccount, settings: Settings):
    """Build an authenticated Google Calendar API service."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as build_service

    encryption = get_encryption_service()
    access_token = encryption.decrypt(account.encrypted_access_token)
    refresh_token = encryption.decrypt(account.encrypted_refresh_token)

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        account.encrypted_access_token = encryption.encrypt(credentials.token)
        account.token_expiry = credentials.expiry

    service = build_service("calendar", "v3", credentials=credentials)
    return service


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


async def list_accounts(
    db: AsyncSession, user_id: uuid.UUID
) -> list[GoogleCalendarAccount]:
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.user_id == user_id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def disconnect_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.id == account_id,
        GoogleCalendarAccount.user_id == user_id,
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("Google Calendar account", "unknown")
    await db.delete(account)
    await db.commit()


# ---------------------------------------------------------------------------
# Calendar listing
# ---------------------------------------------------------------------------


async def list_google_calendars(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID, settings: Settings
) -> list[dict]:
    """List the user's Google calendars from the connected account."""
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.id == account_id,
        GoogleCalendarAccount.user_id == user_id,
        GoogleCalendarAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("Google Calendar account", str(account_id))

    service = await _get_calendar_service(account, settings)
    calendar_list = service.calendarList().list().execute()
    await db.commit()  # Persist any token refresh

    calendars = []
    for cal in calendar_list.get("items", []):
        calendars.append({
            "id": cal["id"],
            "summary": cal.get("summary", ""),
            "description": cal.get("description", ""),
            "primary": cal.get("primary", False),
            "background_color": cal.get("backgroundColor", ""),
        })
    return calendars


async def set_sync_calendar(
    db: AsyncSession,
    account_id: uuid.UUID,
    google_calendar_id: str,
    user_id: uuid.UUID,
) -> GoogleCalendarAccount:
    """Select which Google Calendar to sync with."""
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.id == account_id,
        GoogleCalendarAccount.user_id == user_id,
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("Google Calendar account", str(account_id))

    account.selected_calendar_id = google_calendar_id
    await db.commit()
    await db.refresh(account)
    return account


# ---------------------------------------------------------------------------
# Event sync: push booking to Google Calendar
# ---------------------------------------------------------------------------


async def push_booking_to_google(
    db: AsyncSession,
    booking,
    settings: Settings,
) -> str | None:
    """Push a booking to Google Calendar. Returns the Google event ID."""
    if not settings.google_calendar_sync_enabled:
        return None

    from app.scheduling.models import CalendarBooking

    # Find the booking's calendar and check if it has Google sync enabled
    from app.scheduling.service import get_calendar

    cal = await get_calendar(db, booking.calendar_id)
    if not cal.google_sync_enabled or not cal.google_calendar_id:
        return None

    # Find the Google Calendar account for the calendar creator
    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.user_id == cal.created_by,
        GoogleCalendarAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        return None

    try:
        service = await _get_calendar_service(account, settings)

        event = {
            "summary": f"Booking: {booking.guest_name}",
            "description": (
                f"Guest: {booking.guest_name}\n"
                f"Email: {booking.guest_email}\n"
                f"Phone: {booking.guest_phone or 'N/A'}\n"
                f"Notes: {booking.guest_notes or 'N/A'}"
            ),
            "start": {
                "dateTime": booking.start_time.isoformat(),
                "timeZone": cal.timezone,
            },
            "end": {
                "dateTime": booking.end_time.isoformat(),
                "timeZone": cal.timezone,
            },
            "attendees": [{"email": booking.guest_email}],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 1440},
                ],
            },
        }

        if booking.meeting_location:
            event["location"] = booking.meeting_location

        google_cal_id = cal.google_calendar_id or account.selected_calendar_id or "primary"
        created_event = (
            service.events()
            .insert(calendarId=google_cal_id, body=event, sendUpdates="all")
            .execute()
        )

        event_id = created_event.get("id")
        booking.google_event_id = event_id
        await db.commit()
        return event_id
    except Exception as e:
        logger.warning("Failed to push booking to Google Calendar: %s", e)
        return None


async def delete_google_event(
    db: AsyncSession,
    booking,
    settings: Settings,
) -> bool:
    """Delete a booking's corresponding Google Calendar event."""
    if not booking.google_event_id:
        return False

    from app.scheduling.service import get_calendar

    cal = await get_calendar(db, booking.calendar_id)

    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.user_id == cal.created_by,
        GoogleCalendarAccount.is_active.is_(True),
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        return False

    try:
        service = await _get_calendar_service(account, settings)
        google_cal_id = cal.google_calendar_id or account.selected_calendar_id or "primary"
        service.events().delete(
            calendarId=google_cal_id, eventId=booking.google_event_id
        ).execute()
        await db.commit()
        return True
    except Exception as e:
        logger.warning("Failed to delete Google Calendar event: %s", e)
        return False


# ---------------------------------------------------------------------------
# Pull events from Google Calendar
# ---------------------------------------------------------------------------


async def pull_events_from_google(
    db: AsyncSession,
    account: GoogleCalendarAccount,
    settings: Settings,
) -> int:
    """Pull events from Google Calendar and create calendar events locally."""
    from app.calendar.models import CalendarEvent

    try:
        service = await _get_calendar_service(account, settings)
        google_cal_id = account.selected_calendar_id or "primary"

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()

        # Use incremental sync if we have a sync token
        kwargs = {
            "calendarId": google_cal_id,
            "maxResults": 100,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if account.sync_token:
            kwargs["syncToken"] = account.sync_token
        else:
            kwargs["timeMin"] = time_min

        try:
            events_result = service.events().list(**kwargs).execute()
        except Exception:
            # sync token expired, do full sync
            kwargs.pop("syncToken", None)
            kwargs["timeMin"] = time_min
            events_result = service.events().list(**kwargs).execute()

        events = events_result.get("items", [])
        new_sync_token = events_result.get("nextSyncToken")

        created = 0
        for event in events:
            event_id = event.get("id")
            if not event_id:
                continue

            # Skip if already imported
            existing = await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.google_event_id == event_id
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Parse start/end times
            start_data = event.get("start", {})
            end_data = event.get("end", {})

            start_str = start_data.get("dateTime") or start_data.get("date")
            end_str = end_data.get("dateTime") or end_data.get("date")

            if not start_str:
                continue

            from dateutil.parser import parse as parse_dt

            start_dt = parse_dt(start_str)
            end_dt = parse_dt(end_str) if end_str else start_dt

            cal_event = CalendarEvent(
                created_by=account.user_id,
                title=event.get("summary", "Google Calendar Event"),
                description=event.get("description", ""),
                event_type="meeting",
                date=start_dt.date() if hasattr(start_dt, "date") else start_dt,
                google_event_id=event_id,
            )
            db.add(cal_event)
            created += 1

        if new_sync_token:
            account.sync_token = new_sync_token

        account.last_sync_at = datetime.now(timezone.utc)
        await db.commit()
        return created
    except Exception as e:
        logger.warning("Failed to pull events from Google Calendar: %s", e)
        return 0


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------


async def sync_all_accounts(db: AsyncSession, settings: Settings) -> int:
    """Background job: sync all active Google Calendar accounts."""
    if not settings.google_calendar_sync_enabled:
        return 0

    stmt = select(GoogleCalendarAccount).where(
        GoogleCalendarAccount.is_active.is_(True)
    )
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    total = 0
    for account in accounts:
        try:
            count = await pull_events_from_google(db, account, settings)
            total += count
        except Exception:
            continue
    return total
