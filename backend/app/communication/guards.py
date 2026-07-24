"""Outbound telephony guards: rate limits and recipient allow-listing.

Two fraud/abuse vectors were open before this module:

1. **No outbound rate limit.** A compromised account (or a runaway automation)
   could send unbounded SMS. Twilio bills per segment, on our account.
2. **Arbitrary recipients.** ``send_sms`` matched the destination against a
   contact only to *label* the message — a non-match still sent. That is the
   shape of an SMS-pumping attack: blast traffic at attacker-controlled
   numbers on premium routes.

Both are enforced here, before the Twilio call.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

#: Outbound SMS ceilings per tenant. Deliberately generous for a legitimate
#: small business and ruinous for a pumping attack.
SMS_PER_MINUTE = 10
SMS_PER_HOUR = 100
SMS_PER_DAY = 500

#: Outbound calls per tenant.
CALLS_PER_MINUTE = 5
CALLS_PER_HOUR = 50
CALLS_PER_DAY = 200

#: Only these country codes may be messaged or called. Mirrors the Twilio
#: subaccount geo permissions — defence in depth, so a misconfigured Twilio
#: account is still constrained by the application.
ALLOWED_COUNTRY_CODES = ("+1",)


class TelephonyRateLimited(AppError):
    """429 — a per-tenant outbound rate limit was hit."""

    def __init__(self, window: str, limit: int, channel: str = "SMS"):
        super().__init__(
            code="TELEPHONY_RATE_LIMITED",
            message=(
                f"{channel} rate limit reached ({limit} per {window}). "
                "This protects your account from runaway sending — try again shortly."
            ),
            status_code=429,
        )
        self.window = window
        self.limit = limit


class RecipientNotAllowed(AppError):
    """403 — the destination is not a contact in this tenant."""

    def __init__(self, to_number: str):
        super().__init__(
            code="RECIPIENT_NOT_ALLOWED",
            message=(
                f"{to_number} is not in your contacts. To prevent fraud, messages and calls "
                "can only be sent to saved contacts. Add them as a contact first."
            ),
            status_code=403,
        )


def strip_non_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def is_allowed_destination(to_number: str) -> bool:
    """North America only, matching the subaccount geo permissions."""
    normalized = (to_number or "").strip()
    if normalized.startswith("+"):
        return any(normalized.startswith(cc) for cc in ALLOWED_COUNTRY_CODES)
    # Bare 10/11-digit numbers are treated as NANP.
    digits = strip_non_digits(normalized)
    return len(digits) in (10, 11)


async def _count_since(db: AsyncSession, user: User, since: datetime, direction: str = "outbound") -> int:
    from app.communication.models import SmsMessage

    return await db.scalar(
        select(func.count()).select_from(SmsMessage).where(
            SmsMessage.user_id == user.id,
            SmsMessage.direction == direction,
            SmsMessage.created_at >= since,
        )
    ) or 0


async def enforce_sms_rate_limit(db: AsyncSession, user: User) -> None:
    """Minute / hour / day ceilings on outbound SMS. Raises 429."""
    now = datetime.now(timezone.utc)
    for window, delta, limit in (
        ("minute", timedelta(minutes=1), SMS_PER_MINUTE),
        ("hour", timedelta(hours=1), SMS_PER_HOUR),
        ("day", timedelta(days=1), SMS_PER_DAY),
    ):
        sent = await _count_since(db, user, now - delta)
        if sent >= limit:
            logger.warning(
                "telephony: SMS rate limit hit for user %s — %d in the last %s (limit %d)",
                user.id, sent, window, limit,
            )
            raise TelephonyRateLimited(window, limit, "SMS")


async def enforce_recipient_allowed(
    db: AsyncSession, user: User, to_number: str, *, allow_unknown: bool = False
) -> None:
    """The destination must be a contact this tenant owns.

    ``allow_unknown=True`` is for genuinely inbound-driven replies (answering
    someone who texted us first), where no contact record exists yet.
    """
    if not is_allowed_destination(to_number):
        raise RecipientNotAllowed(to_number)

    if allow_unknown:
        return

    from app.communication.service import _find_contact_by_phone

    contact = await _find_contact_by_phone(db, to_number)
    if contact is None:
        logger.warning(
            "telephony: blocked outbound to %s for user %s — not a saved contact",
            to_number, user.id,
        )
        raise RecipientNotAllowed(to_number)
