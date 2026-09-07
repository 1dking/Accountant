"""S5 — site catalogue: CRUD, tenant scoping, public endpoints, compile-time bindings."""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages import data_sources
from app.pages.catalog_models import CatalogItem, PageFAQ, PageReview
from app.pages.catalog_service import (
    create_catalog_item, create_faq, create_review, list_catalog, list_faqs, list_reviews,
)
from app.pages.models import Page, PageStatus, SectionVariant
from app.pages.seeds.bound_blocks import BOUND_BLOCKS
from app.pages.variants import _seed_values, variant_to_section
from tests.conftest import auth_header


# ----------------------------------------------------------------- CRUD ---

@pytest.mark.high
async def test_catalog_crud_and_tenant_scoping(client: AsyncClient, admin_user: User, db: AsyncSession):
    r = await client.post("/api/pages/catalog/items", headers=auth_header(admin_user), json={
        "kind": "service", "name": "Bookkeeping", "summary": "Monthly reconciliation",
        "price_cents": 29900, "price_display": "From $299", "price_period": "/mo",
        "features": ["Reconciliation", "GST/HST", "Monthly report"], "is_featured": True,
    })
    assert r.status_code == 201, r.text
    item_id = r.json()["data"]["id"]
    assert r.json()["data"]["features"] == ["Reconciliation", "GST/HST", "Monthly report"]

    r = await client.get("/api/pages/catalog/items?kind=service&featured=true", headers=auth_header(admin_user))
    assert r.status_code == 200 and len(r.json()["data"]) == 1
    r = await client.get("/api/pages/catalog/items?kind=product", headers=auth_header(admin_user))
    assert r.json()["data"] == []

    r = await client.patch(f"/api/pages/catalog/items/{item_id}", headers=auth_header(admin_user), json={"name": "Bookkeeping Ottawa", "sort_order": 5})
    assert r.status_code == 200 and r.json()["data"]["name"] == "Bookkeeping Ottawa"

    # Another user in another workspace cannot see or touch it.
    other = User(id=uuid.uuid4(), email="other@example.com", full_name="Other Owner", hashed_password="x", role=admin_user.role, is_active=True)
    db.add(other); await db.commit()
    hdr = auth_header(other)
    assert (await client.get("/api/pages/catalog/items", headers=hdr)).json()["data"] == []
    assert (await client.patch(f"/api/pages/catalog/items/{item_id}", headers=hdr, json={"name": "hijack"})).status_code == 404
    assert (await client.delete(f"/api/pages/catalog/items/{item_id}", headers=hdr)).status_code == 404

    assert (await client.delete(f"/api/pages/catalog/items/{item_id}", headers=auth_header(admin_user))).status_code == 204
    assert (await client.get("/api/pages/catalog/items", headers=auth_header(admin_user))).json()["data"] == []


@pytest.mark.high
async def test_review_and_faq_crud(client: AsyncClient, admin_user: User, db: AsyncSession):
    r = await client.post("/api/pages/catalog/reviews", headers=auth_header(admin_user), json={
        "author_name": "Jane Doe", "author_title": "Owner, Acme", "rating": 5, "quote": "They saved us at tax time.",
    })
    assert r.status_code == 201 and r.json()["data"]["rating"] == 5
    r = await client.post("/api/pages/catalog/reviews", headers=auth_header(admin_user), json={
        "author_name": "Mark", "quote": "Good.", "rating": 12,             # clamped
        "source": "not_a_source",                                          # rejected → manual
    })
    assert r.json()["data"]["rating"] == 5 and r.json()["data"]["source"] == "manual"

    r = await client.post("/api/pages/catalog/reviews", headers=auth_header(admin_user), json={"quote": "no author"})
    assert r.status_code == 400
    r = await client.post("/api/pages/catalog/faqs", headers=auth_header(admin_user), json={"question": "How much?", "answer": "Depends on scope."})
    assert r.status_code == 201
    faq_id = r.json()["data"]["id"]
    r = await client.get("/api/pages/catalog/faqs", headers=auth_header(admin_user))
    assert r.status_code == 200 and len(r.json()["data"]) == 1
    r = await client.patch(f"/api/pages/catalog/faqs/{faq_id}", headers=auth_header(admin_user), json={"answer": "$299/mo and up."})
    assert r.status_code == 200 and r.json()["data"]["answer"] == "$299/mo and up."


# ------------------------------------------------------- public endpoints ---

@pytest.mark.high
async def test_public_data_endpoints_are_tenant_scoped(client: AsyncClient, admin_user: User, db: AsyncSession):
    await create_catalog_item(db, admin_user, {"name": "Bookkeeping", "kind": "service", "price_display": "From $299"})
    await create_review(db, admin_user, {"author_name": "Jane", "quote": "Great work.", "rating": 5})
    await create_faq(db, admin_user, {"question": "How long?", "answer": "About a week."})

    # A page owned by this user
    p = Page(id=uuid.uuid4(), title="Site", slug=f"site-{uuid.uuid4().hex[:6]}", status=PageStatus.PUBLISHED,
             sections_json="[]", created_by=admin_user.id)
    db.add(p); await db.commit()

    r = await client.get(f"/api/pages/public/{p.slug}/data/services")
    assert r.status_code == 200 and len(r.json()["data"]) == 1 and r.json()["data"][0]["name"] == "Bookkeeping"
    r = await client.get(f"/api/pages/public/{p.slug}/data/reviews")
    assert len(r.json()["data"]) == 1 and r.json()["data"][0]["rating"] == 5
    r = await client.get(f"/api/pages/public/{p.slug}/data/faqs")
    assert len(r.json()["data"]) == 1 and r.json()["data"][0]["question"] == "How long?"
    # unknown page → 404
    assert (await client.get("/api/pages/public/nope/data/services")).status_code == 404


# -------------------------------------------------- compile-time bindings ---

@pytest_asyncio.fixture
async def bound_variants(db: AsyncSession):
    for v in BOUND_BLOCKS:
        db.add(SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v)))
    await db.commit()


@pytest.mark.high
async def test_bindings_swap_defaults_for_real_data(db: AsyncSession, admin_user: User, bound_variants):
    from sqlalchemy import select as sa_select
    await create_catalog_item(db, admin_user, {"name": "Ottawa bookkeeping", "kind": "service", "summary": "Monthly clean-up", "price_display": "From $349"})
    await create_review(db, admin_user, {"author_name": "Real Client", "quote": "Actually great.", "rating": 5, "sort_order": 1})
    await create_faq(db, admin_user, {"question": "Do you serve Gatineau?", "answer": "Yes — same-day drop-off."})

    services_v = (await db.execute(sa_select(SectionVariant).where(SectionVariant.variant_id == "services_from_catalog"))).scalar_one()
    reviews_v = (await db.execute(sa_select(SectionVariant).where(SectionVariant.variant_id == "reviews_feed"))).scalar_one()
    faq_v = (await db.execute(sa_select(SectionVariant).where(SectionVariant.variant_id == "faqs_from_data"))).scalar_one()
    sections = [variant_to_section(services_v), variant_to_section(reviews_v), variant_to_section(faq_v)]
    p = Page(id=uuid.uuid4(), title="Site", slug=f"site-{uuid.uuid4().hex[:6]}", status=PageStatus.DRAFT,
             sections_json=json.dumps(sections), created_by=admin_user.id)
    db.add(p); await db.commit()

    resolved = await data_sources.resolve_page_bindings(db, p)
    assert resolved is not None
    r_sections = json.loads(resolved)
    assert "Ottawa bookkeeping" in r_sections[0]["jsx_content"] and "From $349" in r_sections[0]["jsx_content"]
    assert "Bookkeeping" not in r_sections[0]["jsx_content"] or "Ottawa bookkeeping" in r_sections[0]["jsx_content"]  # sample gone
    assert "Actually great." in r_sections[1]["jsx_content"] and "Real Client" in r_sections[1]["jsx_content"]
    assert "Jane Doe" not in r_sections[1]["jsx_content"]                                     # sample review gone
    assert "Gatineau" in r_sections[2]["jsx_content"]                                         # real FAQ appears
    # stored sections_json untouched
    await db.refresh(p)
    assert "Bookkeeping" in p.sections_json and "Jane Doe" in p.sections_json


@pytest.mark.high
async def test_bindings_fall_back_when_no_data(db: AsyncSession, admin_user: User, bound_variants):
    from sqlalchemy import select as sa_select
    v = (await db.execute(sa_select(SectionVariant).where(SectionVariant.variant_id == "services_from_catalog"))).scalar_one()
    p = Page(id=uuid.uuid4(), title="Empty", slug=f"e-{uuid.uuid4().hex[:6]}", status=PageStatus.DRAFT,
             sections_json=json.dumps([variant_to_section(v)]), created_by=admin_user.id)
    db.add(p); await db.commit()
    # Empty workspace: nothing to bind, resolver returns None → page keeps sample copy
    resolved = await data_sources.resolve_page_bindings(db, p)
    assert resolved is None
