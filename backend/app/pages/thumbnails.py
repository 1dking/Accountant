"""Rendered thumbnails for the block library and the template library.

Screenshots via headless Chromium (Playwright, optional dependency
`thumbnails`): each block is compiled as a one-section page with the
real runtime so dynamic blocks show their actual UI; templates are
compiled whole. Output is WebP, stored on R2 (`thumbnails/variants/<id>.webp`,
`thumbnails/templates/<id>.webp`) or, without R2, under
app/pages/static/thumbnails/ and served by public_router.serve_static.

`thumbnail_hash` = sha256(template + default_props + runtime version)
skips unchanged blocks. CLI:

    python -m app.pages.thumbnails --variants [--force] [--id hero_video]
    python -m app.pages.thumbnails --templates
    python -m app.pages.thumbnails --all
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pages.models import PageTemplate, SectionVariant

logger = logging.getLogger(__name__)

VARIANT_SIZE = (1200, 750)     # 16:10, matches the picker card
TEMPLATE_SIZE = (1200, 1500)   # tall crop of the full page
STATIC_DIR = Path(__file__).resolve().parent / "static" / "thumbnails"


class PlaywrightMissing(RuntimeError):
    pass


def _require_playwright():
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError as e:  # pragma: no cover - environment dependent
        raise PlaywrightMissing(
            "playwright is not installed — `pip install playwright && playwright install chromium` "
            "(optional dependency group `thumbnails`)"
        ) from e


def variant_hash(variant: SectionVariant) -> str:
    from app.pages.compiler import PAGES_RUNTIME_VERSION
    payload = json.dumps(
        {
            "t": variant.jsx_template,
            "p": variant.default_props or {},
            "m": getattr(variant, "motion_preset", None),
            "b": getattr(variant, "behaviour", None),
            "r": PAGES_RUNTIME_VERSION,
        },
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_variant_preview_html(variant: SectionVariant, *, locale: str = "en", base_url: str = "") -> str:
    """One-section page for screenshotting. Dynamic blocks get sample
    runtime config so they render a realistic state without an API."""
    from app.pages.compiler import compile_page
    from app.pages.variants import variant_to_section

    section = variant_to_section(variant, locale=locale)
    # Static sample for live blocks (no API in the screenshot sandbox).
    meta = section["metadata"]
    if meta.get("behaviour") == "booking_picker":
        meta["runtime"] = {**(meta.get("runtime") or {}), "CALENDAR_SLUG": "__sample__"}
    page = SimpleNamespace(
        id=uuid.uuid4(), title=variant.display_name, slug="__preview__", description=None,
        meta_title=None, meta_description=None, og_image_url=None, favicon_url=None,
        sections_json=json.dumps([section]), html_content=None, css_content=None,
        js_content=None, custom_head_html=None, created_by=None, website_id=None, locale=locale,
    )
    html = compile_page(page, public_base_url=base_url or "http://127.0.0.1:8000")
    # Screenshots run from an about:blank document (Playwright set_content),
    # so every root-relative URL — runtime bundle, library imagery, the
    # availability call — needs a base. <base> covers img/src/href/fetch.
    return _with_base(html, base_url).replace("</head>", _SAMPLE_DATA_SCRIPT + "</head>", 1)


def _with_base(html: str, base_url: str) -> str:
    if not base_url:
        return html
    return html.replace("<head>", f'<head><base href="{base_url.rstrip("/")}/">', 1)


_SAMPLE_DATA_SCRIPT = """<script>
(function(){
  var realFetch = window.fetch;
  window.fetch = function(url, opts){
    var u = String(url);
    if (u.indexOf('/data/availability') !== -1) {
      var days = [], now = new Date();
      for (var i = 1; i <= 5; i++) {
        var d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
        var slots = [];
        for (var h = 9; h < 16; h++) { slots.push(new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, 0).toISOString()); }
        days.push({ date: d.toISOString().slice(0,10), slots: slots });
      }
      return Promise.resolve(new Response(JSON.stringify({ data: { calendar: { slug: 'sample', name: 'Intro call', duration_minutes: 30, timezone: 'America/Toronto' }, days: days } }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return realFetch.apply(this, arguments);
  };
})();
</script>"""


def build_template_preview_html(template: PageTemplate, *, base_url: str = "") -> str:
    from app.pages.compiler import compile_page

    page = SimpleNamespace(
        id=uuid.uuid4(), title=template.name, slug="__template__", description=template.description,
        meta_title=None, meta_description=None, og_image_url=None, favicon_url=None,
        sections_json=template.sections_json, html_content=template.html_content,
        css_content=template.css_content, js_content=None, custom_head_html=None,
        created_by=None, website_id=None,
    )
    html = compile_page(page, public_base_url=base_url or "http://127.0.0.1:8000")
    html = _with_base(html, base_url)
    return html.replace("{{company_name}}", "Your Business").replace("{{COMPANY_NAME}}", "Your Business")


async def screenshot(html: str, size: tuple[int, int], *, full_page: bool = False, settle_ms: int = 900) -> bytes:
    """Render `html` in headless Chromium and return WebP bytes."""
    _require_playwright()
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
            await page.set_content(html, wait_until="networkidle")
            # Let Tailwind CDN + count-ups + reveal animations settle.
            await page.wait_for_timeout(settle_ms)
            await page.evaluate("window.scrollTo(0, 0)")
            return await page.screenshot(type="jpeg", quality=82, full_page=full_page)
        finally:
            await browser.close()


def _to_webp(jpeg: bytes, max_width: int) -> bytes:
    from io import BytesIO
    from PIL import Image

    im = Image.open(BytesIO(jpeg)).convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, int(im.height * max_width / im.width)))
    out = BytesIO()
    im.save(out, format="WEBP", quality=80, method=4)
    return out.getvalue()


async def store(key: str, body: bytes) -> str:
    """R2 when configured, else the local static dir. Returns a URL."""
    from app.config import Settings
    settings = Settings()
    if getattr(settings, "storage_type", "") == "r2" and getattr(settings, "r2_access_key_id", None):
        from app.pages.publisher import upload_bytes_to_r2
        return await upload_bytes_to_r2(settings, key, body, "image/webp")
    path = STATIC_DIR / Path(key).relative_to("thumbnails")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return f"/api/pages/public/static/{Path(key).as_posix()}"


async def render_variant(db: AsyncSession, variant: SectionVariant, *, force: bool = False, base_url: str = "") -> str | None:
    h = variant_hash(variant)
    if not force and variant.thumbnail_hash == h and variant.preview_thumbnail_url:
        return None
    html = build_variant_preview_html(variant, base_url=base_url)
    jpeg = await screenshot(html, VARIANT_SIZE)
    url = await store(f"thumbnails/variants/{variant.id}.webp", _to_webp(jpeg, 800))
    variant.preview_thumbnail_url = f"{url}?v={h[:8]}"
    variant.thumbnail_hash = h
    variant.thumbnail_rendered_at = datetime.now(timezone.utc)
    await db.commit()
    return variant.preview_thumbnail_url


async def render_template(db: AsyncSession, template: PageTemplate, *, force: bool = False, base_url: str = "") -> str | None:
    payload = (template.sections_json or "") + (template.html_content or "") + (template.css_content or "")
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    meta = json.loads(template.metadata_json or "{}") if template.metadata_json else {}
    if not force and meta.get("thumbnail_hash") == h and template.thumbnail_url:
        return None
    html = build_template_preview_html(template, base_url=base_url)
    jpeg = await screenshot(html, TEMPLATE_SIZE, settle_ms=1200)
    url = await store(f"thumbnails/templates/{template.id.hex}.webp", _to_webp(jpeg, 800))
    template.thumbnail_url = f"{url}?v={h[:8]}"
    meta["thumbnail_hash"] = h
    meta["thumbnail_rendered_at"] = datetime.now(timezone.utc).isoformat()
    template.metadata_json = json.dumps(meta)
    await db.commit()
    return template.thumbnail_url


async def render_all(db: AsyncSession, *, variants: bool = True, templates: bool = True,
                     force: bool = False, only_id: str | None = None, base_url: str = "") -> dict[str, Any]:
    done: dict[str, Any] = {"variants": 0, "templates": 0, "skipped": 0, "failed": []}
    if variants:
        q = select(SectionVariant).where(SectionVariant.is_active.is_(True))
        if only_id:
            q = q.where(SectionVariant.variant_id == only_id)
        for v in (await db.execute(q.order_by(SectionVariant.category, SectionVariant.sort_order))).scalars().all():
            try:
                url = await render_variant(db, v, force=force, base_url=base_url)
                done["variants" if url else "skipped"] += 1
                logger.info("thumbnails.variant %s → %s", v.variant_id, url or "(unchanged)")
            except Exception as e:  # noqa: BLE001
                logger.exception("thumbnails.variant_failed %s", v.variant_id)
                done["failed"].append(f"{v.variant_id}: {e}")
    if templates:
        q = select(PageTemplate).where(PageTemplate.is_active.is_(True))
        for t in (await db.execute(q)).scalars().all():
            try:
                url = await render_template(db, t, force=force, base_url=base_url)
                done["templates" if url else "skipped"] += 1
            except Exception as e:  # noqa: BLE001
                logger.exception("thumbnails.template_failed %s", t.name)
                done["failed"].append(f"template {t.name}: {e}")
    return done


async def _main() -> None:
    import sys
    import types

    sys.modules.setdefault("magic", types.SimpleNamespace(from_buffer=lambda *a, **k: "application/octet-stream", Magic=lambda *a, **k: None))
    ap = argparse.ArgumentParser(description="Render block/template thumbnails")
    ap.add_argument("--variants", action="store_true")
    ap.add_argument("--templates", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--id", help="single variant_id")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000", help="where the runtime bundle is served")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from app.config import Settings
    from app.database import build_engine, build_session_factory

    # Register every model so relationship targets (organizations, users…)
    # resolve when PageTemplate / SectionVariant mappers configure.
    from app.main import create_app  # noqa: F401  (imports all model modules)

    session_factory = build_session_factory(build_engine(Settings().database_url))
    async with session_factory() as db:
        result = await render_all(
            db, variants=args.all or args.variants or bool(args.id), templates=args.all or args.templates,
            force=args.force, only_id=args.id, base_url=args.base_url,
        )
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    asyncio.run(_main())
