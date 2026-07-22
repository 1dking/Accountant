
import logging
import uuid
from datetime import datetime, timezone

import stripe as stripe_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.exceptions import ValidationError

from .models import StripeConnectAccount

logger = logging.getLogger(__name__)


def _configure_stripe(settings: Settings) -> None:
    stripe_lib.api_key = settings.stripe_secret_key


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


async def start_onboarding(
    db: AsyncSession, user: User, settings: Settings, base_url: str = ""
) -> str:
    """Create (or resume) a Stripe Express account and return an onboarding link URL.

    Uses the connected account's own stripe_account_id (not our internal
    user_id) in the return/refresh URLs — same purpose as Gmail's
    state=user_id (letting an unauthenticated redirect resolve back to the
    right row), without putting an internal primary key in a URL.
    """
    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    _configure_stripe(settings)

    result = await db.execute(
        select(StripeConnectAccount).where(StripeConnectAccount.user_id == user.id)
    )
    account_row = result.scalar_one_or_none()

    if account_row is None:
        account = stripe_lib.Account.create(
            type="express",
            email=user.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        )
        account_row = StripeConnectAccount(
            user_id=user.id,
            stripe_account_id=account.id,
        )
        db.add(account_row)
        await db.commit()
        await db.refresh(account_row)
    elif not account_row.is_active:
        # Reconnecting after a disconnect — resume onboarding on the same
        # underlying Stripe account rather than creating a new one.
        account_row.is_active = True
        account_row.disconnected_at = None
        await db.commit()

    origin = base_url.rstrip("/") if base_url else "http://localhost:8000"
    account_link = stripe_lib.AccountLink.create(
        account=account_row.stripe_account_id,
        return_url=f"{origin}/api/integrations/stripe-connect/return/{account_row.stripe_account_id}",
        refresh_url=f"{origin}/api/integrations/stripe-connect/refresh/{account_row.stripe_account_id}",
        type="account_onboarding",
    )
    return account_link.url


async def refresh_account_status(
    db: AsyncSession, stripe_account_id: str, settings: Settings | None = None
) -> StripeConnectAccount | None:
    """Re-fetch the account's onboarding status from Stripe and persist it.

    Called from both the /return redirect (best-effort, for a snappier UI)
    and the account.updated webhook (authoritative — Express's return_url
    fires whether or not onboarding actually finished, so the webhook is
    the real source of truth for "fully onboarded").
    """
    result = await db.execute(
        select(StripeConnectAccount).where(
            StripeConnectAccount.stripe_account_id == stripe_account_id
        )
    )
    account_row = result.scalar_one_or_none()
    if account_row is None:
        return None

    if settings is not None:
        _configure_stripe(settings)
    account = stripe_lib.Account.retrieve(stripe_account_id)
    await _apply_account_fields(db, account_row, account)
    return account_row


async def _apply_account_fields(db: AsyncSession, account_row: StripeConnectAccount, account) -> None:
    was_chargeable = account_row.charges_enabled
    account_row.charges_enabled = bool(account.get("charges_enabled"))
    account_row.payouts_enabled = bool(account.get("payouts_enabled"))
    account_row.details_submitted = bool(account.get("details_submitted"))
    if account_row.charges_enabled and not was_chargeable:
        account_row.onboarding_completed_at = datetime.now(timezone.utc)
    await db.commit()


# ---------------------------------------------------------------------------
# Resolution helpers used by payment-creation call sites
# ---------------------------------------------------------------------------


async def get_connect_account_for_user(
    db: AsyncSession, owner_user_id: uuid.UUID
) -> StripeConnectAccount | None:
    """Raw lookup — returns the row regardless of onboarding/active state."""
    result = await db.execute(
        select(StripeConnectAccount).where(StripeConnectAccount.user_id == owner_user_id)
    )
    return result.scalar_one_or_none()


async def get_active_connect_account_id(
    db: AsyncSession, owner_user_id: uuid.UUID
) -> str | None:
    """Returns the connected account's stripe_account_id ONLY if it is fully
    chargeable and still active. Otherwise None, meaning "use the platform's
    own key" — this is the single fallback seam every payment call site
    goes through.
    """
    account_row = await get_connect_account_for_user(db, owner_user_id)
    if account_row is None or not account_row.is_active or not account_row.charges_enabled:
        return None
    return account_row.stripe_account_id


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


async def disconnect(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Stop routing this user's payments to their connected account.

    Purely local — does not call stripe.Account.delete (irreversible on
    Stripe's side, out of scope). Reconnecting resumes onboarding on the
    same underlying Stripe account.
    """
    account_row = await get_connect_account_for_user(db, user_id)
    if account_row is None:
        return
    account_row.is_active = False
    account_row.disconnected_at = datetime.now(timezone.utc)
    await db.commit()


# ---------------------------------------------------------------------------
# Webhook handling (Connect-scoped endpoint)
# ---------------------------------------------------------------------------


async def handle_connect_webhook_event(
    db: AsyncSession,
    payload: bytes,
    sig_header: str,
    settings: Settings,
) -> dict:
    from app.integrations.stripe.service import (
        _handle_checkout_completed,
        _handle_payment_intent_succeeded,
        _handle_subscription_cancelled,
        _handle_subscription_payment,
    )

    _configure_stripe(settings)

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.stripe_connect_webhook_secret
        )
    except stripe_lib.error.SignatureVerificationError:
        raise ValidationError("Invalid webhook signature")

    event_type = event["type"]
    data_object = event["data"]["object"]
    connected_account_id = event.get("account")

    if event_type == "account.updated":
        await _apply_account_fields_from_event(db, connected_account_id, data_object)
    elif event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data_object, expected_connect_account_id=connected_account_id)
    elif event_type == "payment_intent.succeeded":
        await _handle_payment_intent_succeeded(db, data_object, expected_connect_account_id=connected_account_id)
    elif event_type == "invoice.payment_succeeded":
        await _handle_subscription_payment(db, data_object, expected_connect_account_id=connected_account_id)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_cancelled(db, data_object, expected_connect_account_id=connected_account_id)

    return {"event_type": event_type, "handled": True}


async def _apply_account_fields_from_event(
    db: AsyncSession, connected_account_id: str | None, account_object: dict
) -> None:
    if not connected_account_id:
        return
    result = await db.execute(
        select(StripeConnectAccount).where(
            StripeConnectAccount.stripe_account_id == connected_account_id
        )
    )
    account_row = result.scalar_one_or_none()
    if account_row is None:
        logger.warning("account.updated for unknown connected account %s", connected_account_id)
        return
    await _apply_account_fields(db, account_row, account_object)
