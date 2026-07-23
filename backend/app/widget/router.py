"""FastAPI router for the embeddable email-capture widget (Arivio port).

Design note: the whole widget (button + form) renders inside ONE
same-origin iframe (/embed/{key}, served by our own SPA). Both the
config fetch and the submit happen from JS running inside that iframe
— i.e. same-origin to this API — so no CORS relaxation is needed
anywhere. The third-party page only ever loads widget.js (a <script
src>, not subject to CORS) and an <iframe src>, neither of which CORS
governs. Gated on the existing "forms" flag — a widget without forms
underneath it is meaningless.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.widget import service
from app.widget.schemas import (
    PublicWidgetConfig,
    WidgetConfigResponse,
    WidgetConfigUpdate,
    WidgetSubmitRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Authenticated
# ---------------------------------------------------------------------------


@router.get("/config", response_model=dict)
async def get_my_widget(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    config = await service.get_or_create_config(db, user)
    return {"data": WidgetConfigResponse.model_validate(config)}


@router.put("/config", response_model=dict)
async def update_my_widget(
    data: WidgetConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.MANAGER, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    config = await service.update_config(db, user, data)
    return {"data": WidgetConfigResponse.model_validate(config)}


@router.post("/config/rotate-key", response_model=dict)
async def rotate_widget_key(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.MANAGER, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    config = await service.rotate_key(db, user)
    return {"data": WidgetConfigResponse.model_validate(config)}


# ---------------------------------------------------------------------------
# Public (no auth) — static segments before parameterized ones
# ---------------------------------------------------------------------------


@router.get("/public/{widget_key}/config", response_model=dict)
async def get_public_widget_config(
    widget_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await service.get_public_config(db, widget_key)
    return {
        "data": PublicWidgetConfig(
            mode=config.mode,
            position=config.position,
            button_color=config.button_color or "#2563eb",
            bg_color=config.bg_color or "#ffffff",
            text_color=config.text_color or "#111827",
            greeting_title=config.greeting_title or "Let's talk",
            greeting_message=config.greeting_message or "",
            collect_phone=config.collect_phone,
        )
    }


@router.post("/public/{widget_key}/submit", status_code=201, response_model=dict)
async def submit_public_widget(
    widget_key: str,
    data: WidgetSubmitRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]
    await service.submit(db, widget_key, data, ip_address, user_agent)
    config = await service.get_public_config(db, widget_key)
    return {"data": {"message": config.success_message or "Thanks! We'll be in touch soon."}}
