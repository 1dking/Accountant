"""Block model v2 — S2: public runtime API, compile-time bindings, runtime tags."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core import ratelimit
from app.forms.models import Form, FormSubmission
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.seeds.dynamic_blocks import DYNAMIC_BLOCKS
from app.pages.variants import _seed_values, variant_to_section
from app.scheduling.models import CalendarBooking, SchedulingCalendar


def _seed(variant_id: str) -> dict:
    return next(v for v in DYNAMIC_BLOCKS if v["variant_id"] == variant_id)


@pytest_asyncio.fixture(autouse=True)
def _reset_ratelimit():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest_asyncio.fixture
async def dyn_variants(db: AsyncSession) -> dict[str, SectionVariant]:
    out = {}
    for v in DYNAMIC_BLOCKS:
        row = SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v))
        db.add(row)
        out[v["variant_id"]] = row
    await db.commit()
    return out


@pytest_asyncio.fixture
async def site(db: AsyncSession, admin_user: User, dyn_variants) -> Page:
    sections = [
        variant_to_section(dyn_variants["contact_lead_form"]),
        variant_to_section(dyn_variants["booking_inline_picker"], prop_overrides={"CALENDAR_SLUG": "intro-call", "DAYS": 3}),
        variant_to_section(dyn_variants["team_from_workspace"]),
    ]
    p = Page(id=uuid.uuid4(), title="Acme site", slug=f"acme-{uuid.uuid4().hex[:6]}", status=PageStatus.PUBLISHED,
             sections_json=json.dumps(sections), created_by=admin_user.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest_asyncio.fixture
async def calendar(db: AsyncSession, admin_user: User) -> SchedulingCalendar:
    cal = SchedulingCalendar(id=uuid.uuid4(), name="Intro call", slug="intro-call", duration_minutes=30,
                             buffer_minutes=0, max_advance_days=60, min_notice_hours=0, is_active=True,
                             timezone="America/Toronto", created_by=admin_user.id,
                             availability_json=json.dumps({d: [{"start": "09:00", "end": "12:00"}] for d in
                                                           ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}))
    db.add(cal)
    await db.commit()
    return cal


# ------------------------------------------------------------------ seeds ---

def test_dynamic_seeds_render_cleanly_in_both_locales():
    from app.pages.variants import _TOKEN_RE
    from types import SimpleNamespace
    for v in DYNAMIC_BLOCKS:
        values = _seed_values(v)
        for locale in ("en", "fr-CA"):
            fake = SimpleNamespace(id=v["id"], category=v["category"], variant_id=v["variant_id"], **values)
            sec = variant_to_section(fake, locale=locale)
            leftover = [m for m in _TOKEN_RE.findall(sec["jsx_content"]) if not m.endswith("_URL") and m not in ("VIDEO_EMBED", "MEDIA_EMBED")]
            assert not leftover, f"{v['variant_id']} [{locale}] unresolved tokens: {leftover}"
            assert sec["metadata"]["schema_version"] == 2
        if v.get("behaviour"):
            assert variant_to_section(SimpleNamespace(id=v["id"], category=v["category"], variant_id=v["variant_id"], **values))["metadata"]["behaviour"] == v["behaviour"]


# ---------------------------------------------------------------- compile ---

def test_compile_emits_runtime_and_block_config_only_when_needed(dyn_variants=None):
    from types import SimpleNamespace
    from app.pages.compiler import PAGES_RUNTIME_VERSION, compile_page

    def page_for(sections):
        return SimpleNamespace(id=uuid.uuid4(), title="m", slug="acme", description=None, meta_title=None,
                               meta_description=None, og_image_url=None, favicon_url=None,
                               sections_json=json.dumps(sections), html_content=None, css_content=None,
                               js_content=None, custom_head_html=None, created_by=None, website_id=None)

    v = _seed("booking_inline_picker")
    fake = SimpleNamespace(id=v["id"], category=v["category"], variant_id=v["variant_id"], **_seed_values(v))
    sec = variant_to_section(fake, prop_overrides={"CALENDAR_SLUG": "intro-call"})
    html = compile_page(page_for([sec]))
    assert 'data-block="booking_picker"' in html
    assert "data-block-config=" in html and "CALENDAR_SLUG" in html and "intro-call" in html
    assert f'/api/pages/public/runtime/{PAGES_RUNTIME_VERSION}/runtime.js' in html
    assert f'/api/pages/public/runtime/{PAGES_RUNTIME_VERSION}/runtime.css' in html
    assert 'window.__PAGES__={"slug":"acme","api":"/api/pages/public/acme"' in html

    plain = compile_page(page_for([{"id": "s", "type": "hero", "jsx_content": "<section><h1>x</h1></section>"}]))
    assert "runtime.js" not in plain and "__PAGES__" not in plain and "data-block=" not in plain


def test_runtime_bundle_is_committed_for_current_version():
    from pathlib import Path
    from app.pages.compiler import PAGES_RUNTIME_VERSION
    base = Path(__file__).resolve().parents[2] / "app" / "pages" / "static" / "runtime" / PAGES_RUNTIME_VERSION
    assert (base / "runtime.js").is_file() and (base / "runtime.css").is_file(), (
        f"run `pnpm run build:runtime` in frontend/ — {base} is missing"
    )
    version_ts = (Path(__file__).resolve().parents[3] / "frontend" / "src" / "pages-runtime" / "version.ts").read_text()
    assert f"'{PAGES_RUNTIME_VERSION}'" in version_ts, "frontend RUNTIME_VERSION drifted from PAGES_RUNTIME_VERSION"


@pytest.mark.high
async def test_runtime_asset_served_immutable(client: AsyncClient):
    from app.pages.compiler import PAGES_RUNTIME_VERSION
    resp = await client.get(f"/api/pages/public/runtime/{PAGES_RUNTIME_VERSION}/runtime.js")
    assert resp.status_code == 200, resp.text
    assert "immutable" in resp.headers.get("cache-control", "")
    # traversal attempts never reach a file (httpx normalises the path away
    # from the public router; a raw client hits the segment regex → 404)
    assert (await client.get("/api/pages/public/runtime/../../main.py")).status_code in (400, 401, 404)
    assert (await client.get("/api/pages/public/runtime/2026.09.1/%2e%2e%2fmain.py")).status_code == 404


# --------------------------------------------------------------- bindings ---

@pytest.mark.high
async def test_publish_bindings_fill_team_from_users(db: AsyncSession, site: Page, admin_user: User):
    from app.pages.data_sources import resolve_page_bindings
    resolved = await resolve_page_bindings(db, site)
    assert resolved is not None
    team_sec = next(s for s in json.loads(resolved) if s["metadata"].get("data_source") == "users")
    assert admin_user.full_name in team_sec["jsx_content"]
    assert team_sec["metadata"]["bound_at_publish"] is True
    assert "Alex Brown" not in team_sec["jsx_content"]           # placeholder team replaced
    # stored page untouched
    await db.refresh(site)
    assert "Alex Brown" in site.sections_json


# ------------------------------------------------------------------- lead ---

@pytest.mark.high
async def test_public_lead_creates_contact_submission_and_hidden_form(client: AsyncClient, db: AsyncSession, site: Page, admin_user: User):
    resp = await client.post(f"/api/pages/public/{site.slug}/lead", json={
        "name": "Jane Visitor", "email": "jane@visitor.example.com", "phone": "613-555-0199",
        "message": "Need a quote", "_t": 4200, "_hp": "", "_block": "quote_calc",
        "_quote": {"total": 215, "currency": "CAD", "items": [{"label": "Rooms", "qty": 3, "amount": 135}]},
    })
    assert resp.status_code == 200, resp.text
    sid = resp.json()["data"]["submission_id"]
    sub = (await db.execute(select(FormSubmission).where(FormSubmission.id == uuid.UUID(sid)))).scalar_one()
    form = (await db.execute(select(Form).where(Form.id == sub.form_id))).scalar_one()
    assert form.description == f"__page:{site.id}" and form.created_by == admin_user.id
    assert sub.contact_id is not None
    data = json.loads(sub.data_json)
    assert data["_page"] == site.slug and data["_block"] == "quote_calc" and data["_quote"]["total"] == 215
    assert "_hp" not in data and "_t" not in data
    from app.contacts.models import Contact, ContactActivity
    contact = (await db.execute(select(Contact).where(Contact.id == sub.contact_id))).scalar_one()
    assert contact.email == "jane@visitor.example.com" and contact.created_by == admin_user.id
    notes = (await db.execute(select(ContactActivity).where(ContactActivity.contact_id == contact.id))).scalars().all()
    assert any("Instant quote: 215 CAD" in (n.title or "") for n in notes)

    # Second submission with the same email reuses the form and contact.
    resp2 = await client.post(f"/api/pages/public/{site.slug}/lead", json={"email": "jane@visitor.example.com", "message": "again", "_t": 3000})
    assert resp2.status_code == 200
    forms = (await db.execute(select(Form).where(Form.description == f"__page:{site.id}"))).scalars().all()
    assert len(forms) == 1


@pytest.mark.high
async def test_public_lead_bot_defences_and_validation(client: AsyncClient, db: AsyncSession, site: Page):
    before = (await db.execute(select(FormSubmission))).scalars().all()
    # honeypot filled → silently accepted, nothing stored
    r = await client.post(f"/api/pages/public/{site.slug}/lead", json={"email": "bot@x.com", "_hp": "http://spam", "_t": 9000})
    assert r.status_code == 200 and r.json() == {"ok": True}
    # too fast
    r = await client.post(f"/api/pages/public/{site.slug}/lead", json={"email": "bot@x.com", "_t": 200})
    assert r.status_code == 200 and r.json() == {"ok": True}
    after = (await db.execute(select(FormSubmission))).scalars().all()
    assert len(after) == len(before)
    # empty
    assert (await client.post(f"/api/pages/public/{site.slug}/lead", json={"_t": 5000})).status_code == 400
    # unknown page
    assert (await client.post("/api/pages/public/nope-nope/lead", json={"email": "a@b.co", "_t": 5000})).status_code == 404


@pytest.mark.high
async def test_public_write_rate_limit(client: AsyncClient, site: Page):
    codes = []
    for _ in range(11):
        r = await client.post(f"/api/pages/public/{site.slug}/lead", json={"email": "rl@x.com", "_t": 5000})
        codes.append(r.status_code)
    assert codes[:10] == [200] * 10 and codes[10] == 429


# ------------------------------------------------------------ availability ---

@pytest.mark.high
async def test_public_availability_is_tenant_scoped(client: AsyncClient, db: AsyncSession, site: Page, calendar: SchedulingCalendar, admin_user: User):
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    r = await client.get(f"/api/pages/public/{site.slug}/data/availability?calendar=intro-call&date={tomorrow}&days=2")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["calendar"]["slug"] == "intro-call" and len(data["days"]) == 2
    assert data["days"][0]["date"] == tomorrow and len(data["days"][0]["slots"]) == 6   # 09:00-12:00 / 30 min
    # Hours are the calendar's LOCAL hours: first slot is 09:00 America/Toronto, not 09:00 UTC.
    from zoneinfo import ZoneInfo
    first = datetime.fromisoformat(data["days"][0]["slots"][0]).astimezone(ZoneInfo("America/Toronto"))
    assert (first.hour, first.minute) == (9, 0)
    # Today's list never offers a slot that has already started (create_booking would 409).
    today = datetime.now(timezone.utc).date().isoformat()
    r = await client.get(f"/api/pages/public/{site.slug}/data/availability?calendar=intro-call&date={today}&days=1")
    now = datetime.now(timezone.utc)
    assert all(datetime.fromisoformat(s) >= now for s in r.json()["data"]["days"][0]["slots"])

    # A calendar owned by someone else is refused even though the slug is public.
    other = User(id=uuid.uuid4(), email="other@example.com", full_name="Other Owner", hashed_password="x", role=admin_user.role, is_active=True)
    db.add(other)
    await db.flush()
    db.add(SchedulingCalendar(id=uuid.uuid4(), name="Foreign", slug="foreign-cal", duration_minutes=30, is_active=True,
                              timezone="UTC", created_by=other.id))
    await db.commit()
    r = await client.get(f"/api/pages/public/{site.slug}/data/availability?calendar=foreign-cal")
    assert r.status_code == 403
    assert (await client.get(f"/api/pages/public/{site.slug}/data/availability?calendar=missing")).status_code == 404


# ------------------------------------------------------------------- book ---

@pytest.mark.high
async def test_public_book_creates_booking_and_rejects_taken_slot(client: AsyncClient, db: AsyncSession, site: Page, calendar: SchedulingCalendar):
    from zoneinfo import ZoneInfo
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 30, tzinfo=ZoneInfo("America/Toronto")).astimezone(timezone.utc).isoformat()
    body = {"calendar": "intro-call", "guest_name": "Sam Guest", "guest_email": "sam@guest.example.com",
            "guest_phone": "613-555-0100", "guest_notes": "From the website", "start_time": start}
    r = await client.post(f"/api/pages/public/{site.slug}/book", json=body)
    assert r.status_code == 200, r.text
    bid = r.json()["data"]["booking_id"]
    booking = (await db.execute(select(CalendarBooking).where(CalendarBooking.id == uuid.UUID(bid)))).scalar_one()
    assert booking.calendar_id == calendar.id and booking.guest_email == "sam@guest.example.com"

    # same slot again → 409
    r = await client.post(f"/api/pages/public/{site.slug}/book", json=body)
    assert r.status_code == 409, r.text
    # missing email → 400
    r = await client.post(f"/api/pages/public/{site.slug}/book", json={**body, "guest_email": "nope", "start_time": start})
    assert r.status_code == 400
    # slot no longer offered
    r = await client.get(f"/api/pages/public/{site.slug}/data/availability?calendar=intro-call&date={tomorrow.isoformat()}&days=1")
    assert start not in r.json()["data"]["days"][0]["slots"]
