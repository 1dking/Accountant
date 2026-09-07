"""Anonymous endpoints the published-page runtime talks to.

Mounted at /api/pages/public (registered BEFORE the authed pages router
and without the feature-toggle dependency — a visitor is not a user).
Every route is tenant-scoped by the page slug: the page's `created_by`
owns the form, calendar and data the block may touch, so a page can
never book into someone else's calendar or read another workspace.

    GET  /{slug}/data/company                 public business card
    GET  /{slug}/data/availability?calendar=&date=&days=
    POST /{slug}/lead                         lead form / quote / quiz → contact + submission + FORM_SUBMITTED
    POST /{slug}/book                         booking picker → CalendarBooking (+ APPOINTMENT_BOOKED)
    GET  /runtime/{version}/{file}            the runtime bundle (immutable cache)

Rate limits (core/ratelimit.py): reads 120/min per IP; writes 10/min and
50/day per IP. Lead capture also drops honeypot / sub-1.5s submissions
silently (200 with ok:true so bots learn nothing).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import enforce
from app.dependencies import get_db
from app.pages.models import Page

logger = logging.getLogger(__name__)
router = APIRouter()

READ_LIMITS = ((120, 60.0),)
WRITE_LIMITS = ((10, 60.0), (50, 86400.0))
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_SAFE_SEG = re.compile(r"^[A-Za-z0-9._-]+$")
_MIN_TIME_ON_PAGE_MS = 1500
_MAX_FIELD_LEN = 4000
_MAX_FIELDS = 40


async def _page_by_slug(db: AsyncSession, slug: str) -> Page:
    row = await db.execute(
        select(Page)
        .where(Page.slug == slug)
        .order_by(
            Page.compiled_html_published_at.is_(None),
            Page.compiled_html_published_at.desc(),
            Page.updated_at.desc(),
        )
        .limit(1)
    )
    page = row.scalars().first()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


# ---------------------------------------------------------------- runtime ---

@router.get("/runtime/{version}/{filename}")
async def serve_runtime(version: str, filename: str) -> FileResponse:
    if not _SAFE_SEG.match(version) or not _SAFE_SEG.match(filename):
        raise HTTPException(status_code=404, detail="Not found")
    path = (_STATIC_DIR / "runtime" / version / filename).resolve()
    if not str(path).startswith(str(_STATIC_DIR.resolve())) or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/static/{path:path}")
async def serve_static(path: str) -> FileResponse:
    """Local-dev fallback for thumbnails / library imagery (R2 serves them
    in production). Path-confined to app/pages/static."""
    if not path or any(not _SAFE_SEG.match(seg) for seg in path.split("/")):
        raise HTTPException(status_code=404, detail="Not found")
    target = (_STATIC_DIR / path).resolve()
    if not str(target).startswith(str(_STATIC_DIR.resolve())) or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target, headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------- data ---

@router.get("/{slug}/data/company")
async def public_company(
    slug: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    enforce(request, "pages.read", *READ_LIMITS)
    page = await _page_by_slug(db, slug)
    from app.pages.data_sources import resolve_company
    return {"data": await resolve_company(db, page)}


@router.get("/{slug}/data/availability")
async def public_availability(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    calendar: str = Query(..., description="Calendar slug"),
    date_from: str | None = Query(None, alias="date", description="YYYY-MM-DD (default today)"),
    days: int = Query(7, ge=1, le=31),
) -> dict:
    enforce(request, "pages.read", *READ_LIMITS)
    page = await _page_by_slug(db, slug)
    cal = await _owned_calendar(db, page, calendar)
    from datetime import timedelta
    from app.scheduling.service import get_available_slots

    try:
        start = date.fromisoformat(date_from) if date_from else datetime.now(timezone.utc).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    groups = []
    for i in range(days):
        d = start + timedelta(days=i)
        slots = await get_available_slots(db, cal.id, d.isoformat())
        groups.append({
            "date": d.isoformat(),
            "slots": [s.get("start") if isinstance(s, dict) else s for s in slots],
        })
    return {
        "data": {
            "calendar": {
                "slug": cal.slug, "name": cal.name, "duration_minutes": cal.duration_minutes,
                "timezone": cal.timezone, "description": cal.description,
            },
            "days": groups,
        }
    }


@router.get("/{slug}/data/services")
async def public_services(
    slug: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = Query("service", pattern="^(service|product|plan)$"),
    featured: bool = False,
    limit: int = Query(24, ge=1, le=60),
) -> dict:
    enforce(request, "pages.read", *READ_LIMITS)
    page = await _page_by_slug(db, slug)
    from app.auth.models import User
    from app.pages import catalog_service

    owner = (await db.execute(select(User).where(User.id == page.created_by))).scalar_one_or_none()
    if owner is None:
        return {"data": []}
    items = await catalog_service.list_catalog(db, owner, kind=kind, featured_only=featured, limit=limit)
    return {"data": [catalog_service.catalog_out(i) for i in items]}


@router.get("/{slug}/data/reviews")
async def public_reviews(
    slug: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
    source: str | None = Query(None),
    featured: bool = False,
    min_rating: int | None = Query(None, ge=1, le=5),
    limit: int = Query(12, ge=1, le=60),
) -> dict:
    enforce(request, "pages.read", *READ_LIMITS)
    page = await _page_by_slug(db, slug)
    from app.auth.models import User
    from app.pages import catalog_service

    owner = (await db.execute(select(User).where(User.id == page.created_by))).scalar_one_or_none()
    if owner is None:
        return {"data": []}
    rows = await catalog_service.list_reviews(db, owner, source=source, featured_only=featured, min_rating=min_rating, limit=limit)
    return {"data": [catalog_service.review_out(r) for r in rows]}


@router.get("/{slug}/data/faqs")
async def public_faqs(
    slug: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(None),
    limit: int = Query(40, ge=1, le=100),
) -> dict:
    enforce(request, "pages.read", *READ_LIMITS)
    page = await _page_by_slug(db, slug)
    from app.auth.models import User
    from app.pages import catalog_service

    owner = (await db.execute(select(User).where(User.id == page.created_by))).scalar_one_or_none()
    if owner is None:
        return {"data": []}
    rows = await catalog_service.list_faqs(db, owner, category=category, limit=limit)
    return {"data": [catalog_service.faq_out(f) for f in rows]}


async def _owned_calendar(db: AsyncSession, page: Page, calendar_slug: str):
    from app.scheduling.models import SchedulingCalendar

    row = await db.execute(
        select(SchedulingCalendar).where(
            SchedulingCalendar.slug == calendar_slug,
            SchedulingCalendar.is_active.is_(True),
        )
    )
    cal = row.scalars().first()
    if cal is None:
        raise HTTPException(status_code=404, detail="Calendar not found")
    if cal.created_by != page.created_by:
        # Not this workspace's calendar — refuse rather than leak or book.
        raise HTTPException(status_code=403, detail="Calendar does not belong to this site")
    return cal


# ------------------------------------------------------------------- lead ---

def _clean_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep plain scalar fields (plus the structured _quote/_quiz blobs),
    clamp sizes, drop runtime bookkeeping keys."""
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(payload.items()):
        if i >= _MAX_FIELDS:
            break
        if not isinstance(k, str) or k in ("_hp", "_t"):
            continue
        if k in ("_quote", "_quiz") and isinstance(v, (dict, list)):
            out[k] = json.loads(json.dumps(v)[: _MAX_FIELD_LEN * 4])
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k[:64]] = v[:_MAX_FIELD_LEN] if isinstance(v, str) else v
    return out


async def _page_form(db: AsyncSession, page: Page):
    """Get-or-create the hidden system Form that owns this page's leads,
    so submissions show up in Forms → Submissions and fire workflows."""
    from app.forms.models import Form

    marker = f"__page:{page.id}"
    row = await db.execute(select(Form).where(Form.description == marker, Form.created_by == page.created_by))
    form = row.scalars().first()
    if form is None:
        form = Form(
            id=uuid.uuid4(),
            name=f"Website leads: {page.title}"[:255],
            description=marker,
            fields_json="[]",
            thank_you_type="message",
            is_active=True,
            created_by=page.created_by,
        )
        db.add(form)
        await db.flush()
    return form


@router.post("/{slug}/lead")
async def public_lead(
    slug: str, request: Request, body: dict, db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    enforce(request, "pages.write", *WRITE_LIMITS)
    page = await _page_by_slug(db, slug)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be an object")

    # Bot defences: honeypot filled or submitted faster than a human could.
    hp = body.get("_hp")
    t_ms = body.get("_t")
    if (isinstance(hp, str) and hp.strip()) or (isinstance(t_ms, (int, float)) and t_ms < _MIN_TIME_ON_PAGE_MS):
        logger.info("pages.lead.dropped slug=%s reason=%s", slug, "honeypot" if hp else "too_fast")
        return {"ok": True}

    data = _clean_fields(body)
    if not any(isinstance(v, str) and v.strip() for k, v in data.items() if not k.startswith("_")):
        raise HTTPException(status_code=400, detail="Nothing to submit")
    data["_page"] = page.slug
    block = body.get("_block")
    if isinstance(block, str):
        data["_block"] = block[:64]

    from app.forms.service import _ingest_submission

    form = await _page_form(db, page)
    submission = await _ingest_submission(
        db, form, data,
        request.headers.get("x-forwarded-for", request.client.host if request.client else None),
        request.headers.get("user-agent"),
        source=f"page:{block}" if isinstance(block, str) else "page",
    )

    quote = data.get("_quote")
    if submission.contact_id and isinstance(quote, dict):
        try:
            from app.contacts.models import ActivityType
            from app.contacts.service import log_contact_activity
            total = quote.get("total")
            currency = quote.get("currency") or "CAD"
            lines = quote.get("items") or []
            desc = "; ".join(
                f"{ln.get('label')} × {ln.get('qty')} = {ln.get('amount')}"
                for ln in lines if isinstance(ln, dict)
            )[:2000]
            await log_contact_activity(
                db, contact_id=submission.contact_id, activity_type=ActivityType.NOTE_ADDED,
                title=f"Instant quote: {total} {currency}", description=desc or None,
                reference_type="form_submission", reference_id=submission.id,
            )
            await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("pages.lead.quote_note_failed submission=%s", submission.id)

    return {"ok": True, "data": {"submission_id": str(submission.id)}}


# ------------------------------------------------------------------- book ---

@router.post("/{slug}/book")
async def public_book(
    slug: str, request: Request, body: dict, db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    enforce(request, "pages.write", *WRITE_LIMITS)
    page = await _page_by_slug(db, slug)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be an object")
    cal_slug = body.get("calendar")
    if not isinstance(cal_slug, str) or not cal_slug:
        raise HTTPException(status_code=400, detail="calendar is required")
    cal = await _owned_calendar(db, page, cal_slug)

    from pydantic import ValidationError as PydanticError
    from app.core.exceptions import ValidationError
    from app.scheduling.schemas import BookingCreate
    from app.scheduling.service import create_booking

    try:
        data = BookingCreate(
            guest_name=str(body.get("guest_name") or "").strip()[:255],
            guest_email=str(body.get("guest_email") or "").strip()[:255],
            guest_phone=(str(body.get("guest_phone"))[:50] if body.get("guest_phone") else None),
            guest_notes=(str(body.get("guest_notes"))[:2000] if body.get("guest_notes") else None),
            start_time=body.get("start_time"),
            meeting_type=body.get("meeting_type") if isinstance(body.get("meeting_type"), str) else None,
        )
    except PydanticError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0].get("msg", "Invalid booking"))
    if not data.guest_name or "@" not in data.guest_email:
        raise HTTPException(status_code=400, detail="Name and a valid email are required")
    try:
        booking = await create_booking(db, cal.id, data)
    except ValidationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "ok": True,
        "data": {
            "booking_id": str(booking.id),
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "calendar": cal.name,
            "confirmation_message": cal.confirmation_message,
        },
    }
