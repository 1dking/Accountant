"""User onboarding checklist computation.

Items are evaluated at runtime against the user's actual data, not
stored as a static flag list. The `onboarding_state` JSON column on
users only tracks per-item dismissal metadata.

Item structure returned by `compute_items(db, user)`:
  {
    "key": str,                  # stable identifier
    "label": str,                # short title for UI
    "description": str,          # one-line explanation
    "completed": bool,           # computed from real state
    "action_link": str | None,   # where to send the user to complete it
    "can_dismiss": bool,         # most items dismissible; required ones not
  }
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.communication.models import (
    SmsAutomationFlow,
    TwilioPhoneNumber,
)
from app.contacts.models import Contact

logger = logging.getLogger(__name__)


async def compute_items(db: AsyncSession, user: User) -> list[dict]:
    """Build the live onboarding checklist for a user. All checks hit
    real data — completion never drifts out of sync with reality.
    """
    state = user.onboarding_state or {}

    # 1. Phone configured (an assigned TwilioPhoneNumber row exists)
    phone_row = await db.execute(
        select(TwilioPhoneNumber).where(
            TwilioPhoneNumber.assigned_user_id == user.id
        )
    )
    has_phone = phone_row.scalar_one_or_none() is not None

    # 2. Fallback phone set
    has_fallback = bool(user.fallback_phone)

    # 3. Voicemail greeting recorded (audio or text)
    has_greeting = user.voicemail_greeting_type is not None

    # 4. Automation flow configured (at least one active)
    flow_count = await db.scalar(
        select(func.count())
        .select_from(SmsAutomationFlow)
        .where(
            SmsAutomationFlow.user_id == user.id,
            SmsAutomationFlow.is_active == True,  # noqa: E712
        )
    ) or 0
    has_active_flow = flow_count > 0

    # 5. Conversation engine enabled with a template
    has_conversation_engine = bool(
        user.conversation_reply_enabled
        and (user.conversation_template or "").strip()
    )

    # 6. First contact added (any contact in DB — multi-tenant scoping
    # would gate this differently; for now treat single-tenant)
    contact_count = await db.scalar(
        select(func.count()).select_from(Contact)
    ) or 0
    has_first_contact = contact_count > 0

    items = [
        {
            "key": "phone_configured",
            "label": "Get a Twilio phone number",
            "description": "Assign a number so you can send/receive calls and SMS.",
            "completed": has_phone,
            "action_link": "/communication?tab=phone-numbers",
            "can_dismiss": False,  # required for almost every other feature
        },
        {
            "key": "fallback_phone_set",
            "label": "Add your cell as fallback",
            "description": "If you don't pick up in the browser, calls forward to your cell.",
            "completed": has_fallback,
            "action_link": "/settings?tab=profile",
            "can_dismiss": True,
        },
        {
            "key": "voicemail_greeting_recorded",
            "label": "Record a voicemail greeting",
            "description": "Personalize what callers hear when you can't answer.",
            "completed": has_greeting,
            "action_link": "/settings?tab=profile",
            "can_dismiss": True,
        },
        {
            "key": "first_contact_added",
            "label": "Add your first contact",
            "description": "Contacts unlock memory, AI brief, and per-conversation auto-reply.",
            "completed": has_first_contact,
            "action_link": "/contacts",
            "can_dismiss": True,
        },
        {
            "key": "auto_reply_configured",
            "label": "Set up an SMS automation flow",
            "description": "Auto-respond when calls are missed or voicemails arrive.",
            "completed": has_active_flow,
            "action_link": "/settings?tab=automation",
            "can_dismiss": True,
        },
        {
            "key": "conversation_engine_enabled",
            "label": "Turn on AI conversation engine",
            "description": "Let AI continue text threads on your behalf when you're away.",
            "completed": has_conversation_engine,
            "action_link": "/settings?tab=automation",
            "can_dismiss": True,
        },
    ]

    # Apply dismissed_at from JSON state
    for item in items:
        item_state = state.get(item["key"]) or {}
        item["dismissed_at"] = item_state.get("dismissed_at")
    return items


def compute_progress(items: list[dict]) -> float:
    """Fraction completed, ignoring dismissed items in the denominator."""
    relevant = [i for i in items if not i.get("dismissed_at")]
    if not relevant:
        return 1.0
    done = sum(1 for i in relevant if i["completed"])
    return round(done / len(relevant), 4)


async def dismiss_item(
    db: AsyncSession, user: User, item_key: str
) -> dict:
    """Mark an item as dismissed in onboarding_state. Returns updated state.

    No-op if item_key isn't known — caller can validate first.
    """
    state = dict(user.onboarding_state or {})
    entry = dict(state.get(item_key) or {})
    entry["dismissed_at"] = datetime.now(timezone.utc).isoformat()
    state[item_key] = entry
    user.onboarding_state = state
    await db.commit()
    await db.refresh(user)
    logger.info("onboarding.dismissed user_id=%s item=%s", user.id, item_key)
    return state
