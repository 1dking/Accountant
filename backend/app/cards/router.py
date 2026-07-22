"""FastAPI router for the digital business card (Arivio port).

Public routes coexist on this feature-gated router because
require_feature passes unauthenticated requests through (the proven
forms/scheduling pattern) — static paths registered before /{param}
ones, per forms/router.py convention.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.cards import service
from app.cards.schemas import CardResponse, CardUpdate
from app.cards.vcard import build_vcard
from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import get_current_user, get_db, require_role
from app.documents.storage import LocalStorage

router = APIRouter()

ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
AVATAR_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
MAX_AVATAR_BYTES = 5 * 1024 * 1024


def _storage(request: Request) -> LocalStorage:
    return LocalStorage(request.app.state.settings.storage_path)


# ---------------------------------------------------------------------------
# Authenticated: my card
# ---------------------------------------------------------------------------


@router.get("/me", response_model=dict)
async def get_my_card(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    card = await service.get_or_create_card(db, user)
    return {"data": CardResponse.model_validate(card)}


@router.put("/me", response_model=dict)
async def update_my_card(
    data: CardUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    card = await service.update_card(db, user, data)
    return {"data": CardResponse.model_validate(card)}


@router.get("/slug-check", response_model=dict)
async def check_slug(
    slug: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from sqlalchemy import select

    from app.cards.models import BusinessCard
    from app.cards.service import RESERVED_SLUGS, _slugify

    normalized = _slugify(slug)
    if normalized in RESERVED_SLUGS:
        return {"data": {"slug": normalized, "available": False, "reason": "reserved"}}
    existing = await db.execute(
        select(BusinessCard).where(BusinessCard.slug == normalized, BusinessCard.user_id != user.id)
    )
    taken = existing.scalar_one_or_none() is not None
    return {"data": {"slug": normalized, "available": not taken, "reason": "taken" if taken else None}}


@router.post("/me/avatar", response_model=dict)
async def upload_avatar(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN, Role.MANAGER, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    file: UploadFile = File(...),
) -> dict:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_AVATAR_EXTENSIONS))}"
        )
    content = await file.read()
    if len(content) > MAX_AVATAR_BYTES:
        raise ValidationError("Avatar must be under 5 MB")

    storage = _storage(request)
    path = await storage.save(content, ext)

    card = await service.get_or_create_card(db, user)
    card.avatar_storage_path = path
    await db.commit()
    await db.refresh(card)
    return {"data": CardResponse.model_validate(card)}


# ---------------------------------------------------------------------------
# Public (no auth) — static segments before parameterized ones
# ---------------------------------------------------------------------------


@router.get("/public/{slug}", response_model=dict)
async def get_public_card(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    card = await service.get_public_card(db, slug)
    payload = await service.build_public_payload(db, card)
    return {"data": payload}


@router.get("/public/{slug}/vcard")
async def download_vcard(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    card = await service.get_public_card(db, slug)
    base = str(request.base_url).rstrip("/")
    vcf = build_vcard(
        display_name=card.display_name,
        job_title=card.job_title,
        company_name=card.company_name,
        email=card.email,
        phone=card.phone,
        website=card.website,
        card_url=f"{base}/c/{card.slug}",
    )
    safe_name = card.display_name.replace(" ", "-")
    return Response(
        content=vcf.encode("utf-8"),
        media_type="text/vcard; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.vcf"'},
    )


@router.get("/public/{slug}/manifest")
async def card_manifest(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Per-card PWA manifest — installing the card puts the person's
    name/colors on the home-screen app, not O-Brain's."""
    card = await service.get_public_card(db, slug)
    payload = await service.build_public_payload(db, card)
    return {
        "name": card.display_name,
        "short_name": card.display_name.split()[0] if card.display_name.split() else card.display_name,
        "start_url": f"/c/{card.slug}",
        "display": "standalone",
        "background_color": payload.bg_color,
        "theme_color": payload.bg_color,
        "icons": [
            {"src": "/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }


@router.get("/public/{slug}/avatar")
async def stream_avatar(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    card = await service.get_public_card(db, slug)
    if not card.avatar_storage_path:
        raise NotFoundError("Avatar", slug)
    storage = _storage(request)
    if not await storage.exists(card.avatar_storage_path):
        raise NotFoundError("Avatar", slug)
    data = await storage.read(card.avatar_storage_path)
    ext = card.avatar_storage_path.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=AVATAR_CONTENT_TYPES.get(ext, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=3600"},
    )
