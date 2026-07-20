"""Operator-only, cross-tenant aggregate reads over the event log.

Backs the Pricing Lab's OBrainAdapter (see OBRAIN_EVENT_SPEC.md §5). Every
endpoint here returns data aggregated across ALL accounts on the deployment —
that is deliberately outside the owner-private model the rest of the API
enforces, so it is gated the same way Platform Admin's own endpoints are
(`require_platform_admin`), plus the router-level `require_feature
("platform_admin")` dependency already mounted in main.py. Nothing here
accepts a resource id or returns a single user's private records.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_db
from app.events import service
from app.platform_admin.router import require_platform_admin

router = APIRouter()


@router.get("/accounts")
async def accounts(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {"data": await service.get_accounts(db)}


@router.get("/value-metrics")
async def value_metrics(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {"data": await service.get_value_metrics(db)}


@router.get("/lifecycle")
async def lifecycle_events(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {"data": await service.get_lifecycle_events(db)}


@router.get("/module-usage")
async def module_usage(
    admin: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {"data": await service.get_module_usage(db)}
