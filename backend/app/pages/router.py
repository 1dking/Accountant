"""FastAPI router for the AI page builder module."""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.pages import service
from app.pages.schemas import (
    AIGenerateRequest,
    AIRefineRequest,
    PageCreate,
    PageListItem,
    PageResponse,
    PageUpdate,
    PageVersionResponse,
    PageAnalyticsSummary,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Static paths first
# ---------------------------------------------------------------------------


@router.get("/style-presets")
async def list_style_presets(
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": list(service.STYLE_PRESETS.values())}


@router.get("/section-templates")
async def list_section_templates(
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": service.SECTION_TEMPLATES}


@router.post("/ai/generate", status_code=201)
async def ai_generate(
    data: AIGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    request: Request,
) -> dict:
    settings = request.app.state.settings
    result = await service.ai_generate_page(
        db,
        data.prompt,
        data.style_preset,
        data.primary_color,
        data.font_family,
        data.sections,
        settings=settings,
    )
    return {"data": result}


@router.post("/ai/refine")
async def ai_refine(
    data: AIRefineRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    request: Request,
) -> dict:
    settings = request.app.state.settings
    result = await service.ai_refine_page(
        db,
        data.page_id,
        data.instruction,
        data.section_index,
        settings=settings,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Pages CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_pages(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    pages, total = await service.list_pages(db, page, page_size)
    return {
        "data": [PageListItem.model_validate(p) for p in pages],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("", status_code=201)
async def create_page(
    data: PageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.create_page(db, data, current_user)
    return {"data": PageResponse.model_validate(page)}


@router.get("/{page_id}")
async def get_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    page = await service.get_page(db, page_id)
    return {"data": PageResponse.model_validate(page)}


@router.put("/{page_id}")
async def update_page(
    page_id: uuid.UUID,
    data: PageUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.update_page(db, page_id, data, current_user)
    return {"data": PageResponse.model_validate(page)}


@router.delete("/{page_id}")
async def delete_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_page(db, page_id)
    return {"data": {"message": "Page deleted"}}


@router.post("/{page_id}/publish")
async def publish_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.publish_page(db, page_id, current_user)
    return {"data": PageResponse.model_validate(page)}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/{page_id}/versions")
async def list_versions(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    versions = await service.list_versions(db, page_id)
    return {"data": [PageVersionResponse.model_validate(v) for v in versions]}


@router.post("/{page_id}/versions/{version_id}/restore")
async def restore_version(
    page_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.restore_version(db, page_id, version_id, current_user)
    return {"data": PageResponse.model_validate(page)}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/{page_id}/analytics")
async def get_analytics(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    days: int = Query(30, ge=1, le=365),
) -> dict:
    data = await service.get_page_analytics(db, page_id, days)
    return {"data": PageAnalyticsSummary(**data)}


# ---------------------------------------------------------------------------
# Public page hosting
# ---------------------------------------------------------------------------


@router.get("/public/view/{slug}")
async def view_public_page(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> HTMLResponse:
    page = await service.get_page_by_slug(db, slug)

    # Record view
    await service.record_page_view(
        db,
        page.id,
        visitor_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referrer=request.headers.get("referer"),
    )

    # Build full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.meta_title or page.title}</title>
    <meta name="description" content="{page.meta_description or page.description or ''}">
    {f'<link rel="icon" href="{page.favicon_url}">' if page.favicon_url else ''}
    <style>{page.css_content or ''}</style>
    {page.custom_head_html or ''}
</head>
<body>
    {page.html_content or ''}
    {f'<script>{page.js_content}</script>' if page.js_content else ''}
</body>
</html>"""
    return HTMLResponse(content=html)
