"""Platform-admin management of the block library (block model v2, S3).

Mounted at /api/platform-admin/blocks. Every route requires a platform
admin (same dependency as the rest of platform_admin).

    GET   /                      all blocks (active + disabled) + thumbnail state
    PATCH /{id}                  is_active / sort_order / display_name / description
    POST  /resync                re-seed from code (keeps is_active)
    POST  /{id}/thumbnail        render one thumbnail (501 without Playwright)
    POST  /thumbnails            render all missing/changed thumbnails (background)
    GET   /thumbnails/status     last render run summary
"""
from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_db
from app.pages.models import SectionVariant
from app.platform_admin.router import require_platform_admin

logger = logging.getLogger(__name__)
router = APIRouter()

_render_state: dict[str, Any] = {"running": False, "last": None}


def _block_out(v: SectionVariant) -> dict:
    return {
        "id": v.id,
        "category": v.category,
        "variant_id": v.variant_id,
        "display_name": v.display_name,
        "description": v.description,
        "sort_order": v.sort_order,
        "is_active": bool(v.is_active),
        "schema_version": getattr(v, "schema_version", 1) or 1,
        "behaviour": getattr(v, "behaviour", None),
        "data_source": getattr(v, "data_source", None),
        "motion_preset": getattr(v, "motion_preset", None),
        "capabilities": getattr(v, "capabilities", None) or [],
        "field_count": len(getattr(v, "fields_schema", None) or []),
        "locales": sorted((getattr(v, "locale_props", None) or {}).keys()),
        "preview_thumbnail_url": v.preview_thumbnail_url,
        "thumbnail_rendered_at": (
            v.thumbnail_rendered_at.isoformat() if getattr(v, "thumbnail_rendered_at", None) else None
        ),
        "thumbnail_stale": _is_stale(v),
    }


def _is_stale(v: SectionVariant) -> bool:
    try:
        from app.pages.thumbnails import variant_hash
        return variant_hash(v) != (getattr(v, "thumbnail_hash", None) or "")
    except Exception:  # noqa: BLE001
        return True


@router.get("")
async def list_blocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_platform_admin)],
) -> dict:
    rows = await db.execute(select(SectionVariant).order_by(SectionVariant.category, SectionVariant.sort_order, SectionVariant.display_name))
    blocks = [_block_out(v) for v in rows.scalars().all()]
    cats: dict[str, dict[str, int]] = {}
    for b in blocks:
        c = cats.setdefault(b["category"], {"total": 0, "active": 0, "with_thumbnail": 0})
        c["total"] += 1
        c["active"] += int(b["is_active"])
        c["with_thumbnail"] += int(bool(b["preview_thumbnail_url"]))
    return {"data": blocks, "meta": {"categories": cats, "total": len(blocks), "render": _render_state}}


class BlockPatch(BaseModel):
    is_active: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=10000)
    display_name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


@router.patch("/{block_id}")
async def patch_block(
    block_id: str,
    body: BlockPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> dict:
    v = (await db.execute(select(SectionVariant).where(SectionVariant.id == block_id))).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Block not found")
    changed = body.model_dump(exclude_unset=True)
    for k, val in changed.items():
        setattr(v, k, val)
    await db.commit()
    await db.refresh(v)
    logger.info("platform_admin.block_patched id=%s by=%s changes=%s", block_id, admin.id, list(changed))
    return {"data": _block_out(v)}


@router.post("/resync")
async def resync_blocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> dict:
    from app.pages.variants import resync_variants
    n = await resync_variants(db)
    logger.info("platform_admin.blocks_resynced count=%d by=%s", n, admin.id)
    return {"data": {"synced": n}}


@router.post("/{block_id}/thumbnail")
async def render_block_thumbnail(
    block_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_platform_admin)],
) -> dict:
    v = (await db.execute(select(SectionVariant).where(SectionVariant.id == block_id))).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Block not found")
    from app.pages import thumbnails
    try:
        thumbnails._require_playwright()
    except thumbnails.PlaywrightMissing as e:
        raise HTTPException(status_code=501, detail=str(e))
    from app.config import Settings
    base = Settings().public_base_url or "http://127.0.0.1:8000"
    url = await thumbnails.render_variant(db, v, force=True, base_url=base)
    return {"data": {"preview_thumbnail_url": url}}


async def _render_all_job(session_factory, force: bool) -> None:
    from app.config import Settings
    from app.pages import thumbnails

    _render_state["running"] = True
    try:
        async with session_factory() as db:
            result = await thumbnails.render_all(
                db, variants=True, templates=True, force=force,
                base_url=Settings().public_base_url or "http://127.0.0.1:8000",
            )
        _render_state["last"] = result
    except Exception as e:  # noqa: BLE001
        logger.exception("platform_admin.thumbnails_failed")
        _render_state["last"] = {"error": str(e)}
    finally:
        _render_state["running"] = False


@router.post("/thumbnails")
async def render_all_thumbnails(
    request: Request,
    background: BackgroundTasks,
    _: Annotated[User, Depends(require_platform_admin)],
    force: bool = False,
) -> dict:
    from app.pages import thumbnails
    try:
        thumbnails._require_playwright()
    except thumbnails.PlaywrightMissing as e:
        raise HTTPException(status_code=501, detail=str(e))
    if _render_state["running"]:
        return {"data": {"started": False, "running": True}}
    background.add_task(_render_all_job, request.app.state.session_factory, force)
    await asyncio.sleep(0)
    return {"data": {"started": True, "running": True}}


@router.get("/thumbnails/status")
async def thumbnails_status(_: Annotated[User, Depends(require_platform_admin)]) -> dict:
    return {"data": _render_state}
