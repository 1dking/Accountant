from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing import service
from app.billing.schemas import CheckoutRequest, SubscriptionResponse
from app.dependencies import get_current_user, get_db

router = APIRouter()


@router.get("/subscription")
async def get_subscription(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    sub = await service.get_subscription(db, user)
    return {"data": SubscriptionResponse(**service._payload(sub))}


@router.get("/usage")
async def get_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Current usage against the plan's caps. `limit: null` means unlimited."""
    from app.billing.limits import get_usage_summary

    return {"data": await get_usage_summary(db, user)}


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = request.app.state.settings
    base_url = str(request.base_url).rstrip("/")
    result = await service.create_checkout(db, user, body.plan_key, body.period, settings, base_url)
    return {"data": result}


@router.get("/verify")
async def verify(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_id: str = Query(...),
) -> dict:
    result = await service.verify_checkout(db, user, session_id, request.app.state.settings)
    return {"data": result}


@router.post("/portal")
async def portal(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    origin = str(request.base_url).rstrip("/")
    result = await service.create_portal(db, user, request.app.state.settings, f"{origin}/settings?tab=billing")
    return {"data": result}


@router.get("/ai-credits")
async def get_ai_credits(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Remaining AI credits for this billing month.

    Backs the usage meter in Settings -> Plan & Billing. 1 credit = $0.001 of
    estimated model spend; ``estimated_spend_usd`` is the human-readable form.
    """
    from app.billing.ai_meter import get_usage

    return {"data": await get_usage(db, user)}


# ---------------------------------------------------------------------------
# Telephony credit (prepaid) + A2P 10DLC
# ---------------------------------------------------------------------------


@router.get("/telephony/credit")
async def telephony_credit(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Prepaid telephony balance and auto top-up settings."""
    from app.billing import telephony_credits

    return {"data": await telephony_credits.summary(db, user)}


@router.get("/telephony/rates")
async def telephony_rates(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """What THIS tenant pays per unit, after plan and tenant overrides.

    Sell price only — our cost is operator-only and is not exposed here.
    """
    from app.billing.ai_meter import tenant_key_for
    from app.billing.limits import get_plan_key
    from app.billing.rate_card import full_card

    card = await full_card(
        db, tenant_key=tenant_key_for(user), plan_key=await get_plan_key(db, user)
    )
    return {
        "data": [
            {
                "unit": r["unit"],
                "label": r["label"],
                "price_usd": r["sell_price_usd"],
                "is_enabled": r["is_enabled"],
            }
            for r in card
        ]
    }


@router.post("/telephony/topup")
async def telephony_topup(
    body: dict,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Start a Stripe Checkout to buy telephony credit."""
    from app.billing import telephony_credits

    amount = float(body.get("amount_usd") or 0)
    result = await telephony_credits.create_topup_checkout(
        db, user, amount, request.app.state.settings, str(request.base_url).rstrip("/")
    )
    return {"data": result}


@router.get("/telephony/topup/verify")
async def telephony_topup_verify(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_id: str = Query(...),
) -> dict:
    """Confirm a top-up on return from Stripe, independent of the webhook."""
    from app.billing import telephony_credits

    return {
        "data": await telephony_credits.verify_topup(
            db, user, session_id, request.app.state.settings
        )
    }


@router.put("/telephony/auto-topup")
async def set_auto_topup(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Enable/disable auto top-up and set the threshold and amount."""
    from app.billing import telephony_credits
    from app.billing.rate_card import to_micros

    row = await telephony_credits.get_or_create(db, user)
    if "enabled" in body:
        row.auto_topup_enabled = bool(body["enabled"])
    if body.get("threshold_usd") is not None:
        row.auto_topup_threshold_micros = to_micros(body["threshold_usd"])
    if body.get("amount_usd") is not None:
        row.auto_topup_amount_micros = to_micros(body["amount_usd"])
    await db.commit()
    return {"data": await telephony_credits.summary(db, user)}


@router.get("/telephony/ledger")
async def telephony_ledger(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """This tenant's telephony transactions. Sell price only, never our cost."""
    from sqlalchemy import select as _select

    from app.billing.ai_meter import tenant_key_for
    from app.billing.models import TelephonyLedgerEntry
    from app.billing.rate_card import usd

    rows = (
        await db.execute(
            _select(TelephonyLedgerEntry)
            .where(TelephonyLedgerEntry.tenant_key == tenant_key_for(user))
            .order_by(TelephonyLedgerEntry.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "data": [
            {
                "id": str(r.id),
                "type": r.entry_type,
                "unit": r.unit,
                "quantity": r.quantity,
                "amount_usd": usd(r.billed_micros),
                "balance_after_usd": usd(r.balance_after_micros),
                "description": r.description,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.get("/telephony/a2p")
async def a2p_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """A2P 10DLC registration status and what the tenant should do next."""
    from app.communication import a2p

    return {"data": await a2p.status_for(db, user)}


@router.post("/telephony/a2p")
async def a2p_submit(
    body: dict,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Submit A2P 10DLC brand + campaign registration for this tenant."""
    from app.communication import a2p

    await a2p.submit_registration(db, user, body, request.app.state.settings)
    return {"data": await a2p.status_for(db, user)}
