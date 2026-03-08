"""Business logic for the native calendar & scheduling module."""

import json
import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.scheduling.models import (
    BookingStatus,
    CalendarBooking,
    CalendarMember,
    CalendarType,
    MeetingType,
    SchedulingCalendar,
)


def _slugify(text: str) -> str:
    import re

    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


# ---------------------------------------------------------------------------
# Calendar CRUD
# ---------------------------------------------------------------------------


async def create_calendar(db: AsyncSession, data, user) -> SchedulingCalendar:
    slug = data.slug or _slugify(data.name)
    cal = SchedulingCalendar(
        id=uuid.uuid4(),
        name=data.name,
        slug=slug,
        description=data.description,
        calendar_type=CalendarType(data.calendar_type) if data.calendar_type else CalendarType.PERSONAL,
        duration_minutes=data.duration_minutes or 30,
        buffer_minutes=data.buffer_minutes or 0,
        max_advance_days=data.max_advance_days or 60,
        min_notice_hours=data.min_notice_hours or 1,
        availability_json=data.availability_json,
        timezone=data.timezone or "America/New_York",
        confirmation_message=data.confirmation_message,
        reminder_enabled=data.reminder_enabled if data.reminder_enabled is not None else True,
        google_calendar_id=data.google_calendar_id,
        google_sync_enabled=data.google_sync_enabled or False,
        created_by=user.id,
    )
    db.add(cal)

    # Auto-add creator as member
    member = CalendarMember(
        id=uuid.uuid4(),
        calendar_id=cal.id,
        user_id=user.id,
        is_active=True,
        priority=0,
    )
    db.add(member)

    await db.commit()
    await db.refresh(cal)
    return cal


async def list_calendars(db: AsyncSession, user_id: uuid.UUID, page: int, page_size: int):
    count_q = select(func.count(SchedulingCalendar.id))
    total = (await db.execute(count_q)).scalar() or 0

    q = select(SchedulingCalendar).order_by(SchedulingCalendar.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    calendars = result.scalars().all()
    return calendars, total


async def get_calendar(db: AsyncSession, calendar_id: uuid.UUID) -> SchedulingCalendar:
    result = await db.execute(
        select(SchedulingCalendar).where(SchedulingCalendar.id == calendar_id)
    )
    cal = result.scalar_one_or_none()
    if cal is None:
        raise NotFoundError("SchedulingCalendar", str(calendar_id))
    return cal


async def get_calendar_by_slug(db: AsyncSession, slug: str) -> SchedulingCalendar:
    result = await db.execute(
        select(SchedulingCalendar).where(
            SchedulingCalendar.slug == slug,
            SchedulingCalendar.is_active == True,
        )
    )
    cal = result.scalar_one_or_none()
    if cal is None:
        raise NotFoundError("SchedulingCalendar", slug)
    return cal


async def update_calendar(
    db: AsyncSession, calendar_id: uuid.UUID, data
) -> SchedulingCalendar:
    cal = await get_calendar(db, calendar_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "calendar_type" and value:
            value = CalendarType(value)
        setattr(cal, field, value)
    await db.commit()
    await db.refresh(cal)
    return cal


async def delete_calendar(db: AsyncSession, calendar_id: uuid.UUID) -> None:
    cal = await get_calendar(db, calendar_id)
    await db.delete(cal)
    await db.commit()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def add_member(
    db: AsyncSession, calendar_id: uuid.UUID, user_id: uuid.UUID, priority: int = 0
) -> CalendarMember:
    member = CalendarMember(
        id=uuid.uuid4(),
        calendar_id=calendar_id,
        user_id=user_id,
        is_active=True,
        priority=priority,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(
    db: AsyncSession, calendar_id: uuid.UUID, member_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(CalendarMember).where(
            CalendarMember.id == member_id,
            CalendarMember.calendar_id == calendar_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundError("CalendarMember", str(member_id))
    await db.delete(member)
    await db.commit()


async def list_members(db: AsyncSession, calendar_id: uuid.UUID):
    q = (
        select(CalendarMember)
        .where(CalendarMember.calendar_id == calendar_id)
        .order_by(CalendarMember.priority)
    )
    result = await db.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


async def create_booking(
    db: AsyncSession, calendar_id: uuid.UUID, data
) -> CalendarBooking:
    cal = await get_calendar(db, calendar_id)

    start = data.start_time
    end = start + timedelta(minutes=cal.duration_minutes)

    # Round-robin assignment
    assigned_user_id = None
    if cal.calendar_type == CalendarType.ROUND_ROBIN:
        assigned_user_id = await _get_round_robin_assignee(db, calendar_id)

    # Try to match contact by email
    contact_id = await _match_contact_by_email(db, data.guest_email)

    # Parse meeting type
    meeting_type = None
    if hasattr(data, "meeting_type") and data.meeting_type:
        try:
            meeting_type = MeetingType(data.meeting_type)
        except (ValueError, KeyError):
            meeting_type = None

    booking = CalendarBooking(
        id=uuid.uuid4(),
        calendar_id=calendar_id,
        contact_id=contact_id,
        assigned_user_id=assigned_user_id or cal.created_by,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        guest_phone=getattr(data, "guest_phone", None),
        guest_notes=getattr(data, "guest_notes", None),
        start_time=start,
        end_time=end,
        status=BookingStatus.CONFIRMED,
        meeting_type=meeting_type,
        meeting_location=getattr(data, "meeting_location", None),
        reschedule_token=secrets.token_urlsafe(32),
        cancel_token=secrets.token_urlsafe(32),
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def list_bookings(
    db: AsyncSession,
    calendar_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    count_q = select(func.count(CalendarBooking.id))
    q = select(CalendarBooking)

    if calendar_id:
        count_q = count_q.where(CalendarBooking.calendar_id == calendar_id)
        q = q.where(CalendarBooking.calendar_id == calendar_id)

    if status:
        count_q = count_q.where(CalendarBooking.status == BookingStatus(status))
        q = q.where(CalendarBooking.status == BookingStatus(status))

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(CalendarBooking.start_time.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    bookings = result.scalars().all()
    return bookings, total


async def get_booking(db: AsyncSession, booking_id: uuid.UUID) -> CalendarBooking:
    result = await db.execute(
        select(CalendarBooking).where(CalendarBooking.id == booking_id)
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise NotFoundError("CalendarBooking", str(booking_id))
    return booking


async def update_booking(
    db: AsyncSession, booking_id: uuid.UUID, data
) -> CalendarBooking:
    booking = await get_booking(db, booking_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            value = BookingStatus(value)
        setattr(booking, field, value)
    await db.commit()
    await db.refresh(booking)
    return booking


async def cancel_booking(
    db: AsyncSession, booking_id: uuid.UUID, reason: str | None = None
) -> CalendarBooking:
    booking = await get_booking(db, booking_id)
    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = reason
    await db.commit()
    await db.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# Available slots
# ---------------------------------------------------------------------------


async def get_available_slots(
    db: AsyncSession, calendar_id: uuid.UUID, date_str: str
) -> list[dict]:
    """Get available booking slots for a specific date."""
    cal = await get_calendar(db, calendar_id)

    # Parse availability config
    availability = json.loads(cal.availability_json) if cal.availability_json else None
    if not availability:
        # Default: Mon-Fri 9am-5pm
        availability = {
            "monday": [{"start": "09:00", "end": "17:00"}],
            "tuesday": [{"start": "09:00", "end": "17:00"}],
            "wednesday": [{"start": "09:00", "end": "17:00"}],
            "thursday": [{"start": "09:00", "end": "17:00"}],
            "friday": [{"start": "09:00", "end": "17:00"}],
        }

    from datetime import date as date_type

    target_date = date_type.fromisoformat(date_str)
    day_name = target_date.strftime("%A").lower()
    day_slots = availability.get(day_name, [])

    if not day_slots:
        return []

    # Get existing bookings for that day
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    existing = await db.execute(
        select(CalendarBooking).where(
            CalendarBooking.calendar_id == calendar_id,
            CalendarBooking.start_time >= day_start,
            CalendarBooking.start_time < day_end,
            CalendarBooking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING]),
        )
    )
    booked = existing.scalars().all()
    booked_times = [(b.start_time, b.end_time) for b in booked]

    slots = []
    for slot_range in day_slots:
        start_h, start_m = map(int, slot_range["start"].split(":"))
        end_h, end_m = map(int, slot_range["end"].split(":"))

        current = datetime(
            target_date.year, target_date.month, target_date.day,
            start_h, start_m, 0, tzinfo=timezone.utc,
        )
        range_end = datetime(
            target_date.year, target_date.month, target_date.day,
            end_h, end_m, 0, tzinfo=timezone.utc,
        )

        while current + timedelta(minutes=cal.duration_minutes) <= range_end:
            slot_end = current + timedelta(minutes=cal.duration_minutes)

            # Check for conflicts
            conflict = any(
                current < be and slot_end > bs for bs, be in booked_times
            )

            if not conflict:
                # Also check buffer
                buffer_start = current - timedelta(minutes=cal.buffer_minutes)
                buffer_end = slot_end + timedelta(minutes=cal.buffer_minutes)
                buffer_conflict = any(
                    buffer_start < be and buffer_end > bs for bs, be in booked_times
                )
                if not buffer_conflict:
                    slots.append({"start": current.isoformat(), "end": slot_end.isoformat()})

            current += timedelta(minutes=cal.duration_minutes + cal.buffer_minutes)

    return slots


# ---------------------------------------------------------------------------
# Round-robin assignment
# ---------------------------------------------------------------------------


async def _get_round_robin_assignee(
    db: AsyncSession, calendar_id: uuid.UUID
) -> uuid.UUID | None:
    """Pick the next member with the fewest recent bookings."""
    members = await list_members(db, calendar_id)
    active_members = [m for m in members if m.is_active]
    if not active_members:
        return None

    # Count bookings per member in the last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    counts = {}
    for member in active_members:
        count = (
            await db.execute(
                select(func.count(CalendarBooking.id)).where(
                    CalendarBooking.calendar_id == calendar_id,
                    CalendarBooking.assigned_user_id == member.user_id,
                    CalendarBooking.created_at >= cutoff,
                )
            )
        ).scalar() or 0
        counts[member.user_id] = count

    # Return member with fewest bookings
    return min(counts, key=counts.get)


async def _match_contact_by_email(
    db: AsyncSession, email: str
) -> uuid.UUID | None:
    """Try to match a booking guest to an existing contact."""
    from app.contacts.models import Contact

    result = await db.execute(
        select(Contact.id).where(func.lower(Contact.email) == email.lower())
    )
    row = result.scalar_one_or_none()
    return row


# ---------------------------------------------------------------------------
# Reminders (called by scheduler)
# ---------------------------------------------------------------------------


async def get_bookings_needing_reminders(db: AsyncSession) -> list[CalendarBooking]:
    """Get confirmed bookings that need 24h or 1h reminders."""
    now = datetime.now(timezone.utc)
    h24 = now + timedelta(hours=24)
    h1 = now + timedelta(hours=1)

    q = select(CalendarBooking).where(
        CalendarBooking.status == BookingStatus.CONFIRMED,
        CalendarBooking.start_time > now,
    )
    result = await db.execute(q)
    bookings = result.scalars().all()

    needs_reminder = []
    for b in bookings:
        start = b.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        if not b.reminder_24h_sent and start <= h24:
            needs_reminder.append(b)
        elif not b.reminder_1h_sent and start <= h1:
            needs_reminder.append(b)

    return needs_reminder


async def mark_reminder_sent(
    db: AsyncSession, booking_id: uuid.UUID, reminder_type: str
) -> None:
    booking = await get_booking(db, booking_id)
    if reminder_type == "24h":
        booking.reminder_24h_sent = True
    elif reminder_type == "1h":
        booking.reminder_1h_sent = True
    await db.commit()


# ---------------------------------------------------------------------------
# Public token-based booking access (reschedule / cancel)
# ---------------------------------------------------------------------------


async def get_booking_by_reschedule_token(
    db: AsyncSession, token: str
) -> CalendarBooking:
    result = await db.execute(
        select(CalendarBooking).where(CalendarBooking.reschedule_token == token)
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise NotFoundError("Booking", token)
    return booking


async def get_booking_by_cancel_token(
    db: AsyncSession, token: str
) -> CalendarBooking:
    result = await db.execute(
        select(CalendarBooking).where(CalendarBooking.cancel_token == token)
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise NotFoundError("Booking", token)
    return booking


async def reschedule_booking(
    db: AsyncSession, token: str, new_start_time: datetime
) -> CalendarBooking:
    """Reschedule a booking using the public reschedule token."""
    booking = await get_booking_by_reschedule_token(db, token)
    if booking.status == BookingStatus.CANCELLED:
        raise NotFoundError("Booking", token)

    cal = await get_calendar(db, booking.calendar_id)
    duration = timedelta(minutes=cal.duration_minutes)

    booking.start_time = new_start_time
    booking.end_time = new_start_time + duration
    booking.status = BookingStatus.CONFIRMED
    # Reset reminders for the new time
    booking.reminder_24h_sent = False
    booking.reminder_1h_sent = False
    await db.commit()
    await db.refresh(booking)
    return booking


async def cancel_booking_by_token(
    db: AsyncSession, token: str, reason: str | None = None
) -> CalendarBooking:
    """Cancel a booking using the public cancel token."""
    booking = await get_booking_by_cancel_token(db, token)
    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = reason or "Cancelled by guest"
    await db.commit()
    await db.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------


def generate_ics(booking: CalendarBooking, calendar_name: str, org_name: str = "") -> str:
    """Generate an .ics calendar invite for a booking."""
    uid = str(booking.id)
    start = booking.start_time
    end = booking.end_time

    # Format datetimes as iCalendar UTC format
    def fmt(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")

    location = booking.meeting_location or ""
    summary = f"{calendar_name} with {booking.guest_name}"
    description = booking.guest_notes or ""
    if booking.meeting_type:
        mt = booking.meeting_type.value if hasattr(booking.meeting_type, "value") else str(booking.meeting_type)
        description = f"Meeting type: {mt}\\n{description}".strip()

    now_stamp = fmt(datetime.now(timezone.utc))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{org_name or 'Accountant'}//Scheduling//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        f"ORGANIZER;CN={org_name}:mailto:noreply@example.com",
        f"ATTENDEE;CN={booking.guest_name}:mailto:{booking.guest_email}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines)


# ---------------------------------------------------------------------------
# Booking confirmation & reminder emails
# ---------------------------------------------------------------------------


async def send_booking_confirmation(
    db: AsyncSession, booking: CalendarBooking
) -> bool:
    """Send confirmation email with .ics attachment for a booking."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        from app.email.service import get_default_config, send_email, render_template
        from app.settings.service import get_company_settings

        smtp_config = await get_default_config(db)
        company = await get_company_settings(db)
        org_name = company.company_name if company and company.company_name else "Our Team"

        cal = await get_calendar(db, booking.calendar_id)
        ics_content = generate_ics(booking, cal.name, org_name)

        start_fmt = booking.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC")
        meeting_type_label = ""
        if booking.meeting_type:
            mt = booking.meeting_type.value if hasattr(booking.meeting_type, "value") else str(booking.meeting_type)
            meeting_type_label = mt.replace("_", " ").title()

        # Build reschedule / cancel URLs using public base URL
        from app.config import Settings as _Settings

        try:
            _settings = _Settings()
            base_url = _settings.public_base_url.rstrip("/")
        except Exception:
            base_url = "http://localhost:5173"

        reschedule_url = f"{base_url}/booking/reschedule/{booking.reschedule_token}" if booking.reschedule_token else ""
        cancel_url = f"{base_url}/booking/cancel/{booking.cancel_token}" if booking.cancel_token else ""

        html_body = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Booking Confirmed</h2>
        <p>Hi {booking.guest_name},</p>
        <p>Your appointment with <strong>{org_name}</strong> has been confirmed:</p>
        <table style="border-collapse: collapse; margin: 16px 0;">
          <tr><td style="padding: 8px 16px; font-weight: bold;">Date &amp; Time</td><td style="padding: 8px 16px;">{start_fmt}</td></tr>
          <tr><td style="padding: 8px 16px; font-weight: bold;">Duration</td><td style="padding: 8px 16px;">{cal.duration_minutes} minutes</td></tr>
          {f'<tr><td style="padding: 8px 16px; font-weight: bold;">Type</td><td style="padding: 8px 16px;">{meeting_type_label}</td></tr>' if meeting_type_label else ''}
          {f'<tr><td style="padding: 8px 16px; font-weight: bold;">Location</td><td style="padding: 8px 16px;">{booking.meeting_location}</td></tr>' if booking.meeting_location else ''}
        </table>
        <p>You can manage your booking using the links below:</p>
        <p>
          <a href="{reschedule_url}" style="color: #2563eb;">Reschedule</a> |
          <a href="{cancel_url}" style="color: #dc2626;">Cancel</a>
        </p>
        <p>See you then!</p>
        <p style="color: #666; font-size: 12px;">{org_name}</p>
        </body></html>
        """

        attachments = [
            ("invite.ics", ics_content.encode("utf-8"), "text/calendar"),
        ]

        await send_email(
            smtp_config,
            booking.guest_email,
            f"Booking Confirmed: {cal.name} on {booking.start_time.strftime('%b %d')}",
            html_body,
            attachments,
        )

        booking.confirmation_sent = True
        await db.commit()
        return True
    except Exception as e:
        logger.warning("Failed to send booking confirmation: %s", e)
        return False


async def send_booking_reminder(
    db: AsyncSession, booking: CalendarBooking, reminder_type: str
) -> bool:
    """Send a reminder email for an upcoming booking."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        from app.email.service import get_default_config, send_email
        from app.settings.service import get_company_settings

        smtp_config = await get_default_config(db)
        company = await get_company_settings(db)
        org_name = company.company_name if company and company.company_name else "Our Team"

        cal = await get_calendar(db, booking.calendar_id)
        time_label = "24 hours" if reminder_type == "24h" else "1 hour"
        start_fmt = booking.start_time.strftime("%A, %B %d at %I:%M %p UTC")

        html_body = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Appointment Reminder</h2>
        <p>Hi {booking.guest_name},</p>
        <p>This is a reminder that your appointment with <strong>{org_name}</strong> is in <strong>{time_label}</strong>.</p>
        <table style="border-collapse: collapse; margin: 16px 0;">
          <tr><td style="padding: 8px 16px; font-weight: bold;">Date & Time</td><td style="padding: 8px 16px;">{start_fmt}</td></tr>
          <tr><td style="padding: 8px 16px; font-weight: bold;">Duration</td><td style="padding: 8px 16px;">{cal.duration_minutes} minutes</td></tr>
        </table>
        <p>See you soon!</p>
        <p style="color: #666; font-size: 12px;">{org_name}</p>
        </body></html>
        """

        await send_email(
            smtp_config,
            booking.guest_email,
            f"Reminder: {cal.name} — {start_fmt}",
            html_body,
        )

        await mark_reminder_sent(db, booking.id, reminder_type)
        return True
    except Exception as e:
        logger.warning("Failed to send booking reminder (%s): %s", reminder_type, e)
        return False
