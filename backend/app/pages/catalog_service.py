"""Site catalogue CRUD — services, reviews, FAQs. All queries are
tenant-scoped by (org_id, created_by): a user in an org sees every
sibling's rows; a solo user sees their own only. The pages resolvers
call the same list_* helpers so what shows in the admin UI matches
what's baked into the compiled page."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from app.auth.models import User
from app.pages.catalog_models import CatalogItem, PageFAQ, PageReview

_SLUG = re.compile(r"[^a-z0-9]+")

CATALOG_KINDS = ("service", "product", "plan")
REVIEW_SOURCES = ("manual", "google", "facebook", "yelp", "linkedin")


def slugify(text: str) -> str:
    s = _SLUG.sub("-", (text or "").lower()).strip("-")
    return s[:200] or "item"


def _scope(query: Select, model, owner: User) -> Select:
    """Filter by (org_id, created_by). Used for reads AND writes so the
    endpoints refuse to touch another workspace's rows."""
    if owner.org_id:
        return query.where(model.org_id == owner.org_id)
    return query.where(model.created_by == owner.id)


async def _owner_of_page(db: AsyncSession, page_owner_id: uuid.UUID) -> User | None:
    return (await db.execute(select(User).where(User.id == page_owner_id))).scalar_one_or_none()


# ---------------------------------------------------------------- catalog ---

async def list_catalog(
    db: AsyncSession, owner: User, *, kind: str | None = None,
    featured_only: bool = False, limit: int | None = None,
) -> list[CatalogItem]:
    q = select(CatalogItem).where(CatalogItem.is_active.is_(True))
    q = _scope(q, CatalogItem, owner)
    if kind:
        q = q.where(CatalogItem.kind == kind)
    if featured_only:
        q = q.where(CatalogItem.is_featured.is_(True))
    q = q.order_by(CatalogItem.sort_order, CatalogItem.name)
    if limit:
        q = q.limit(int(limit))
    return list((await db.execute(q)).scalars().all())


async def get_catalog_item(db: AsyncSession, owner: User, item_id: uuid.UUID) -> CatalogItem | None:
    q = select(CatalogItem).where(CatalogItem.id == item_id)
    return (await db.execute(_scope(q, CatalogItem, owner))).scalar_one_or_none()


async def create_catalog_item(db: AsyncSession, owner: User, data: dict) -> CatalogItem:
    kind = data.get("kind") or "service"
    if kind not in CATALOG_KINDS:
        raise ValueError(f"kind must be one of {CATALOG_KINDS}")
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    features = data.get("features")
    row = CatalogItem(
        id=uuid.uuid4(),
        kind=kind,
        name=name[:255],
        slug=(data.get("slug") or slugify(name))[:255],
        summary=(data.get("summary") or None) and str(data["summary"])[:500],
        description=data.get("description"),
        price_cents=int(data["price_cents"]) if data.get("price_cents") is not None else None,
        price_display=(data.get("price_display") or None) and str(data["price_display"])[:50],
        price_period=(data.get("price_period") or None) and str(data["price_period"])[:20],
        currency=(data.get("currency") or "CAD")[:3].upper(),
        features_json=json.dumps([str(f)[:200] for f in features][:20]) if isinstance(features, list) else None,
        image_url=(data.get("image_url") or None),
        cta_text=(data.get("cta_text") or None) and str(data["cta_text"])[:60],
        cta_href=(data.get("cta_href") or None) and str(data["cta_href"])[:500],
        stripe_price_id=(data.get("stripe_price_id") or None),
        booking_slug=(data.get("booking_slug") or None),
        category=(data.get("category") or None) and str(data["category"])[:80],
        sort_order=int(data.get("sort_order") or 100),
        is_featured=bool(data.get("is_featured", False)),
        is_active=bool(data.get("is_active", True)),
        created_by=owner.id,
        org_id=owner.org_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_catalog_item(db: AsyncSession, owner: User, item_id: uuid.UUID, data: dict) -> CatalogItem:
    row = await get_catalog_item(db, owner, item_id)
    if row is None:
        raise LookupError("catalog item not found")
    _apply_patch(row, data, {
        "kind": (lambda v: v if v in CATALOG_KINDS else row.kind),
        "name": (lambda v: str(v)[:255]),
        "slug": (lambda v: str(v)[:255]),
        "summary": (lambda v: str(v)[:500] if v else None),
        "description": (lambda v: v),
        "price_cents": (lambda v: int(v) if v is not None else None),
        "price_display": (lambda v: str(v)[:50] if v else None),
        "price_period": (lambda v: str(v)[:20] if v else None),
        "currency": (lambda v: str(v)[:3].upper() if v else "CAD"),
        "image_url": (lambda v: v or None),
        "cta_text": (lambda v: str(v)[:60] if v else None),
        "cta_href": (lambda v: str(v)[:500] if v else None),
        "stripe_price_id": (lambda v: v or None),
        "booking_slug": (lambda v: v or None),
        "category": (lambda v: str(v)[:80] if v else None),
        "sort_order": (lambda v: int(v) if v is not None else row.sort_order),
        "is_featured": bool,
        "is_active": bool,
    })
    if "features" in data:
        f = data["features"]
        row.features_json = json.dumps([str(x)[:200] for x in f][:20]) if isinstance(f, list) else None
    await db.commit()
    await db.refresh(row)
    return row


async def delete_catalog_item(db: AsyncSession, owner: User, item_id: uuid.UUID) -> bool:
    row = await get_catalog_item(db, owner, item_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


# ---------------------------------------------------------------- reviews ---

async def list_reviews(
    db: AsyncSession, owner: User, *, source: str | None = None,
    featured_only: bool = False, min_rating: int | None = None, limit: int | None = None,
) -> list[PageReview]:
    q = select(PageReview).where(PageReview.is_active.is_(True))
    q = _scope(q, PageReview, owner)
    if source:
        q = q.where(PageReview.source == source)
    if featured_only:
        q = q.where(PageReview.is_featured.is_(True))
    if min_rating:
        q = q.where(PageReview.rating >= int(min_rating))
    q = q.order_by(PageReview.sort_order, PageReview.reviewed_at.desc().nullslast() if hasattr(PageReview.reviewed_at, "desc") else PageReview.reviewed_at.desc())
    if limit:
        q = q.limit(int(limit))
    return list((await db.execute(q)).scalars().all())


async def get_review(db: AsyncSession, owner: User, review_id: uuid.UUID) -> PageReview | None:
    q = select(PageReview).where(PageReview.id == review_id)
    return (await db.execute(_scope(q, PageReview, owner))).scalar_one_or_none()


async def create_review(db: AsyncSession, owner: User, data: dict) -> PageReview:
    quote = str(data.get("quote") or "").strip()
    author = str(data.get("author_name") or "").strip()
    if not quote or not author:
        raise ValueError("author_name and quote are required")
    source = str(data.get("source") or "manual").strip().lower()
    if source not in REVIEW_SOURCES:
        source = "manual"
    rating = data.get("rating")
    if rating is not None:
        rating = max(1, min(5, int(rating)))
    row = PageReview(
        id=uuid.uuid4(),
        author_name=author[:120],
        author_title=(str(data.get("author_title"))[:120] if data.get("author_title") else None),
        author_avatar_url=(data.get("author_avatar_url") or None),
        rating=rating,
        quote=quote[:4000],
        source=source,
        source_url=(data.get("source_url") or None),
        sort_order=int(data.get("sort_order") or 100),
        is_featured=bool(data.get("is_featured", False)),
        is_active=bool(data.get("is_active", True)),
        created_by=owner.id,
        org_id=owner.org_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_review(db: AsyncSession, owner: User, review_id: uuid.UUID, data: dict) -> PageReview:
    row = await get_review(db, owner, review_id)
    if row is None:
        raise LookupError("review not found")
    _apply_patch(row, data, {
        "author_name": (lambda v: str(v)[:120]),
        "author_title": (lambda v: str(v)[:120] if v else None),
        "author_avatar_url": (lambda v: v or None),
        "rating": (lambda v: max(1, min(5, int(v))) if v is not None else None),
        "quote": (lambda v: str(v)[:4000]),
        "source": (lambda v: v if v in REVIEW_SOURCES else row.source),
        "source_url": (lambda v: v or None),
        "sort_order": (lambda v: int(v) if v is not None else row.sort_order),
        "is_featured": bool,
        "is_active": bool,
    })
    await db.commit()
    await db.refresh(row)
    return row


async def delete_review(db: AsyncSession, owner: User, review_id: uuid.UUID) -> bool:
    row = await get_review(db, owner, review_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


# ------------------------------------------------------------------- faqs ---

async def list_faqs(
    db: AsyncSession, owner: User, *, category: str | None = None, limit: int | None = None,
) -> list[PageFAQ]:
    q = select(PageFAQ).where(PageFAQ.is_active.is_(True))
    q = _scope(q, PageFAQ, owner)
    if category:
        q = q.where(PageFAQ.category == category)
    q = q.order_by(PageFAQ.sort_order, PageFAQ.question)
    if limit:
        q = q.limit(int(limit))
    return list((await db.execute(q)).scalars().all())


async def get_faq(db: AsyncSession, owner: User, faq_id: uuid.UUID) -> PageFAQ | None:
    q = select(PageFAQ).where(PageFAQ.id == faq_id)
    return (await db.execute(_scope(q, PageFAQ, owner))).scalar_one_or_none()


async def create_faq(db: AsyncSession, owner: User, data: dict) -> PageFAQ:
    q = str(data.get("question") or "").strip()
    a = str(data.get("answer") or "").strip()
    if not q or not a:
        raise ValueError("question and answer are required")
    row = PageFAQ(
        id=uuid.uuid4(),
        question=q[:500],
        answer=a[:8000],
        category=(str(data.get("category"))[:80] if data.get("category") else None),
        sort_order=int(data.get("sort_order") or 100),
        is_active=bool(data.get("is_active", True)),
        created_by=owner.id,
        org_id=owner.org_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_faq(db: AsyncSession, owner: User, faq_id: uuid.UUID, data: dict) -> PageFAQ:
    row = await get_faq(db, owner, faq_id)
    if row is None:
        raise LookupError("faq not found")
    _apply_patch(row, data, {
        "question": (lambda v: str(v)[:500]),
        "answer": (lambda v: str(v)[:8000]),
        "category": (lambda v: str(v)[:80] if v else None),
        "sort_order": (lambda v: int(v) if v is not None else row.sort_order),
        "is_active": bool,
    })
    await db.commit()
    await db.refresh(row)
    return row


async def delete_faq(db: AsyncSession, owner: User, faq_id: uuid.UUID) -> bool:
    row = await get_faq(db, owner, faq_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


# --------------------------------------------------------------- serialise ---

def catalog_out(item: CatalogItem) -> dict:
    features: list[str] = []
    if item.features_json:
        try:
            features = [str(f) for f in json.loads(item.features_json) if f]
        except Exception:  # noqa: BLE001
            features = []
    return {
        "id": str(item.id), "kind": item.kind, "name": item.name, "slug": item.slug,
        "summary": item.summary, "description": item.description,
        "price_cents": item.price_cents, "price_display": item.price_display,
        "price_period": item.price_period, "currency": item.currency,
        "features": features, "image_url": item.image_url,
        "cta_text": item.cta_text, "cta_href": item.cta_href,
        "stripe_price_id": item.stripe_price_id, "booking_slug": item.booking_slug,
        "category": item.category, "sort_order": item.sort_order,
        "is_featured": bool(item.is_featured), "is_active": bool(item.is_active),
    }


def review_out(r: PageReview) -> dict:
    return {
        "id": str(r.id), "author_name": r.author_name, "author_title": r.author_title,
        "author_avatar_url": r.author_avatar_url, "rating": r.rating, "quote": r.quote,
        "source": r.source, "source_url": r.source_url,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "sort_order": r.sort_order, "is_featured": bool(r.is_featured), "is_active": bool(r.is_active),
    }


def faq_out(f: PageFAQ) -> dict:
    return {
        "id": str(f.id), "question": f.question, "answer": f.answer,
        "category": f.category, "sort_order": f.sort_order, "is_active": bool(f.is_active),
    }


# --------------------------------------------------------------- internals ---

def _apply_patch(row, data: dict, spec: dict[str, Any]) -> None:
    for key, coerce in spec.items():
        if key in data:
            setattr(row, key, coerce(data[key]))
