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
