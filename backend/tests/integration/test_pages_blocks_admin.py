"""Block model v2 — S3: platform-admin block library, thumbnails (no browser), imagery manifest."""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages import imagery
from app.pages.models import SectionVariant
from app.pages.seeds.dynamic_blocks import DYNAMIC_BLOCKS
from app.pages.variants import _seed_values
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def blocks(db: AsyncSession) -> list[SectionVariant]:
    out = []
    for v in DYNAMIC_BLOCKS[:4]:
        row = SectionVariant(id=v["id"], category=v["category"], variant_id=v["variant_id"], is_active=True, **_seed_values(v))
        db.add(row)
        out.append(row)
    await db.commit()
    return out


@pytest.mark.high
async def test_admin_lists_patches_and_hides_disabled_blocks(client: AsyncClient, admin_user: User, blocks, db: AsyncSession):
    r = await client.get("/api/platform-admin/blocks", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["total"] == 4 and "contact" in body["meta"]["categories"]
    row = next(b for b in body["data"] if b["variant_id"] == "contact_lead_form")
    assert row["behaviour"] == "lead_form" and row["field_count"] > 5 and row["locales"] == ["fr-CA"]
    assert row["thumbnail_stale"] is True and row["preview_thumbnail_url"] is None

    r = await client.patch(f"/api/platform-admin/blocks/{row['id']}", headers=auth_header(admin_user), json={"is_active": False, "sort_order": 999})
    assert r.status_code == 200 and r.json()["data"]["is_active"] is False
    # gone from the picker feed
    r = await client.get("/api/pages/variants?category=contact", headers=auth_header(admin_user))
    assert all(v["variant_id"] != "contact_lead_form" for v in r.json()["data"])
    # resync keeps the admin's is_active decision
    r = await client.post("/api/platform-admin/blocks/resync", headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["data"]["synced"] >= 4
    v = (await db.execute(select(SectionVariant).where(SectionVariant.variant_id == "contact_lead_form"))).scalar_one()
    await db.refresh(v)
    assert v.is_active is False
    assert (await client.patch("/api/platform-admin/blocks/nope", headers=auth_header(admin_user), json={"is_active": True})).status_code == 404


@pytest.mark.high
async def test_admin_blocks_require_admin(client: AsyncClient, blocks):
    assert (await client.get("/api/platform-admin/blocks")).status_code == 401


def test_variant_preview_html_is_a_complete_page_with_runtime(blocks=None):
    from types import SimpleNamespace
    from app.pages.thumbnails import build_variant_preview_html, variant_hash

    v = next(x for x in DYNAMIC_BLOCKS if x["variant_id"] == "booking_inline_picker")
    fake = SimpleNamespace(id=v["id"], category=v["category"], variant_id=v["variant_id"], thumbnail_hash=None, **_seed_values(v))
    html = build_variant_preview_html(fake, base_url="http://127.0.0.1:8000")
    assert html.startswith("<!DOCTYPE html>") and 'data-block="booking_picker"' in html
    assert '<base href="http://127.0.0.1:8000/">' in html                     # root-relative URLs resolve in set_content docs
    assert 'src="/api/pages/public/runtime/' in html
    assert "/data/availability" in html                                        # sample-data stub for the screenshot
    assert "__sample__" in html
    h1 = variant_hash(fake)
    fake.default_props = {**fake.default_props, "HEADLINE": "changed"}
    assert variant_hash(fake) != h1


def test_apply_imagery_fills_slots_from_pools_and_manifest(tmp_path, monkeypatch):
    manifest = tmp_path / "imagery_manifest.json"
    manifest.write_text(json.dumps({
        "pools": {"gallery": ["/g1.webp", "/g2.webp"], "team": ["/t1.webp"], "before_after": ["/b.webp", "/a.webp"]},
        "slots": {"gallery_x": {"ITEMS[1].IMAGE_URL": "/explicit.webp"}},
        "stock_fallback": {"hero": ["/stock-hero.webp"]},
    }))
    monkeypatch.setattr(imagery, "_MANIFEST", manifest)
    imagery.reset_cache()

    schema = [
        {"key": "HERO_URL", "type": "image"},
        {"key": "ITEMS", "type": "list", "item_fields": [{"key": "IMAGE_URL", "type": "image"}, {"key": "NAME", "type": "text"}]},
        {"key": "KEEP_URL", "type": "image"},
    ]
    props = {
        "HERO_URL": "data:image/svg+xml,placeholder",
        "ITEMS": [{"IMAGE_URL": "", "NAME": "a"}, {"IMAGE_URL": "https://images.unsplash.com/x", "NAME": "b"}, {"IMAGE_URL": "", "NAME": "c"}],
        "KEEP_URL": "https://cdn.example.com/mine.webp",
    }
    out = imagery.apply_imagery("gallery_x", "gallery", props, schema)
    assert out["HERO_URL"] == "/g1.webp"                       # gallery category → gallery pool
    assert out["ITEMS"][0]["IMAGE_URL"] == "/g2.webp"          # round-robin continues
    assert out["ITEMS"][1]["IMAGE_URL"] == "/explicit.webp"    # explicit slot wins
    assert out["ITEMS"][2]["IMAGE_URL"] == "/g1.webp"          # wraps
    assert out["KEEP_URL"] == "https://cdn.example.com/mine.webp"  # real URLs untouched
    assert props["HERO_URL"].startswith("data:")               # input not mutated

    hero = imagery.apply_imagery("hero_y", "hero", {"IMAGE_URL": ""}, [{"key": "IMAGE_URL", "type": "image"}])
    assert hero["IMAGE_URL"] == "/stock-hero.webp"             # stock fallback when the pool is empty
    ba = imagery.apply_imagery("ba", "gallery", {"BEFORE_URL": "", "AFTER_URL": ""},
                               [{"key": "BEFORE_URL", "type": "image"}, {"key": "AFTER_URL", "type": "image"}])
    assert (ba["BEFORE_URL"], ba["AFTER_URL"]) == ("/b.webp", "/a.webp")
    imagery.reset_cache()


def test_plan_batch_lists_only_missing_images(tmp_path, monkeypatch):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"pools": {"team": ["/1", "/2"]}}))
    monkeypatch.setattr(imagery, "_MANIFEST", manifest)
    imagery.reset_cache()
    plan = imagery.plan_batch()
    total = sum(len(p["prompts"]) for p in imagery.PROMPTS.values())
    assert total == 72
    assert len(plan) == total - 2
    assert all(p["pool"] != "team" or p["index"] >= 2 for p in plan)
    imagery.record_result("team", 2, "/3")
    assert imagery.load_manifest()["pools"]["team"] == ["/1", "/2", "/3"]
    imagery.reset_cache()
