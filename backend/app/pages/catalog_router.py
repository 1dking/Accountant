"""Authed CRUD for the site catalogue (services, reviews, FAQs).

Mounted at /api/pages/catalog. Read-only mirrors for these live on the
anonymous /api/pages/public/{slug}/data/... endpoints (public_router):
the same list_* helpers back both, so what the owner sees in the admin
matches what a visitor gets on the site.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_db, require_role
from app.pages import catalog_service as svc

router = APIRouter()
_ADMIN_OR_TEAM = require_role([Role.ADMIN, Role.TEAM_MEMBER])
UserDep = Annotated[User, Depends(_ADMIN_OR_TEAM)]
DBDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------- catalog ---

@router.get("/items")
async def list_items(
    db: DBDep, user: UserDep,
    kind: str | None = Query(None, description="service | product | plan"),
    featured: bool = False,
    limit: int | None = Query(None, ge=1, le=200),
) -> dict:
    rows = await svc.list_catalog(db, user, kind=kind, featured_only=featured, limit=limit)
    return {"data": [svc.catalog_out(r) for r in rows]}


@router.post("/items", status_code=201)
async def create_item(body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.create_catalog_item(db, user, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": svc.catalog_out(row)}


@router.patch("/items/{item_id}")
async def patch_item(item_id: uuid.UUID, body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.update_catalog_item(db, user, item_id, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": svc.catalog_out(row)}


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, db: DBDep, user: UserDep) -> None:
    if not await svc.delete_catalog_item(db, user, item_id):
        raise HTTPException(status_code=404, detail="Item not found")


# ---------------------------------------------------------------- reviews ---

@router.get("/reviews")
async def list_reviews_route(
    db: DBDep, user: UserDep,
    source: str | None = Query(None),
    featured: bool = False,
    min_rating: int | None = Query(None, ge=1, le=5),
    limit: int | None = Query(None, ge=1, le=200),
) -> dict:
    rows = await svc.list_reviews(db, user, source=source, featured_only=featured, min_rating=min_rating, limit=limit)
    return {"data": [svc.review_out(r) for r in rows]}


@router.post("/reviews", status_code=201)
async def create_review_route(body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.create_review(db, user, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": svc.review_out(row)}


@router.patch("/reviews/{review_id}")
async def patch_review_route(review_id: uuid.UUID, body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.update_review(db, user, review_id, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"data": svc.review_out(row)}


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review_route(review_id: uuid.UUID, db: DBDep, user: UserDep) -> None:
    if not await svc.delete_review(db, user, review_id):
        raise HTTPException(status_code=404, detail="Review not found")


# ------------------------------------------------------------------- faqs ---

@router.get("/faqs")
async def list_faqs_route(
    db: DBDep, user: UserDep,
    category: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
) -> dict:
    rows = await svc.list_faqs(db, user, category=category, limit=limit)
    return {"data": [svc.faq_out(r) for r in rows]}


@router.post("/faqs", status_code=201)
async def create_faq_route(body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.create_faq(db, user, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": svc.faq_out(row)}


@router.patch("/faqs/{faq_id}")
async def patch_faq_route(faq_id: uuid.UUID, body: dict, db: DBDep, user: UserDep) -> dict:
    try:
        row = await svc.update_faq(db, user, faq_id, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"data": svc.faq_out(row)}


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq_route(faq_id: uuid.UUID, db: DBDep, user: UserDep) -> None:
    if not await svc.delete_faq(db, user, faq_id):
        raise HTTPException(status_code=404, detail="FAQ not found")
