"""Static publish — compile a page + upload to R2.

Reads page.sections_json (Pages v2) or falls back to page.html_content
(legacy). Compiles via app.pages.compiler.compile_page, uploads the
resulting HTML to R2 at `pages/{slug}/index.html`, updates the page
row with the publish artifacts.

Serve happens via /api/pages/p/{slug} which reads page.compiled_html
directly from the DB (R2 is the durable copy; DB caches for sub-ms
serve).

R2 upload happens via boto3 put_object with a deterministic key
rather than going through StorageBackend.save() which auto-generates
random keys. Small blast radius — the publisher is the only call
site that needs key control.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.pages.compiler import compile_and_hash
from app.pages.models import Page, PageStatus

logger = logging.getLogger(__name__)


async def _upload_html_to_r2(
    settings: Settings, key: str, html: str,
) -> None:
    """Upload HTML bytes to a specific R2 key. Falls back to writing
    to local storage_path when storage_type != 'r2'.

    Direct boto3 call rather than going through StorageBackend because
    the storage class's save() generates random keys; we want
    deterministic `pages/{slug}/index.html`.
    """
    body = html.encode("utf-8")
    if settings.storage_type == "r2" and settings.r2_access_key_id:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        await asyncio.to_thread(
            client.put_object,
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=body,
            ContentType="text/html; charset=utf-8",
        )
    else:
        # Local fallback: write under storage_path/pages/{slug}/index.html
        import os
        full = os.path.join(settings.storage_path or "./data/documents", key)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        await asyncio.to_thread(_write_file, full, body)


def _write_file(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


async def upload_bytes_to_r2(
    settings: Settings, key: str, body: bytes, content_type: str,
) -> str:
    """Generic R2 upload — used by media picker for image/video files.
    Returns a public URL the browser can fetch. Falls back to a
    local-storage path served via /api/documents/... when R2 isn't
    configured (dev mode).

    Reuses the boto3 client + storage_path conventions from
    _upload_html_to_r2 so we don't have two parallel upload paths.
    """
    if settings.storage_type == "r2" and settings.r2_access_key_id:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        await asyncio.to_thread(
            client.put_object,
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        # Public URL — assumes the R2 bucket has a public custom domain
        # or the public URL pattern is configured via r2_public_base.
        base = getattr(settings, "r2_public_base", None) or settings.r2_endpoint
        return f"{base.rstrip('/')}/{settings.r2_bucket_name}/{key}"
    # Local fallback — relative path; the docs router can serve it.
    import os
    full = os.path.join(settings.storage_path or "./data/documents", key)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    await asyncio.to_thread(_write_file, full, body)
    return f"/api/documents/raw/{key}"


async def publish_page_static(
    db: AsyncSession,
    page_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
) -> dict:
    """Compile + upload + update page row.

    Returns dict: { page_id, slug, r2_key, live_url, content_hash,
                    published_at, was_unchanged }
    Raises ValueError if the page doesn't belong to user_id or has no
    content to compile.
    """
    row = await db.execute(select(Page).where(Page.id == page_id))
    page = row.scalar_one_or_none()
    if page is None:
        raise ValueError("Page not found")
    if page.created_by != user_id:
        raise ValueError("Page not owned by user")

    # Load company settings for JSON-LD Organization. Best-effort; the
    # compiler degrades gracefully when company_settings is None.
    company_settings = None
    try:
        from app.settings.service import get_company_settings
        company_settings = await get_company_settings(db)
    except Exception as exc:
        logger.info(
            "publish.company_settings_lookup_failed page_id=%s err=%s — "
            "compiling without organization schema",
            page_id, exc,
        )

    # Pre-fetch animation defaults for variants referenced by this
    # page's sections. Lets legacy sections (inserted before Commit 4
    # added animation snapshots) still animate at publish time.
    from app.pages.variants import fetch_variant_animations_for_page
    variant_animations = await fetch_variant_animations_for_page(
        db, page.sections_json,
    )

    public_base_url = settings.public_base_url or "https://accountant.ocidm.io"
    html, content_hash = compile_and_hash(
        page,
        company_settings=company_settings,
        public_base_url=public_base_url,
        variant_animations=variant_animations,
    )

    # Short-circuit: if compiled_html hash matches what we already have,
    # don't re-upload (R2 PUTs cost money + invalidate CDN cache).
    if (
        page.compiled_html
        and len(page.compiled_html) == len(html)
        and page.compiled_html == html
    ):
        logger.info(
            "publish.unchanged page_id=%s — skipping upload", page_id
        )
        return {
            "page_id": str(page_id),
            "slug": page.slug,
            "r2_key": page.compiled_html_r2_key,
            "live_url": f"{public_base_url.rstrip('/')}/api/pages/p/{page.slug}",
            "content_hash": content_hash,
            "published_at": (
                page.compiled_html_published_at.isoformat()
                if page.compiled_html_published_at else None
            ),
            "was_unchanged": True,
        }

    r2_key = f"pages/{page.slug}/index.html"
    try:
        await _upload_html_to_r2(settings, r2_key, html)
    except Exception as exc:
        logger.exception(
            "publish.r2_upload_failed page_id=%s key=%s err=%s",
            page_id, r2_key, exc,
        )
        raise

    now = datetime.now(timezone.utc)
    page.compiled_html = html
    page.compiled_html_r2_key = r2_key
    page.compiled_html_published_at = now
    page.status = PageStatus.PUBLISHED
    await db.commit()

    live_url = f"{public_base_url.rstrip('/')}/api/pages/p/{page.slug}"
    logger.info(
        "publish.complete page_id=%s slug=%s r2_key=%s hash=%s",
        page_id, page.slug, r2_key, content_hash[:12],
    )
    return {
        "page_id": str(page_id),
        "slug": page.slug,
        "r2_key": r2_key,
        "live_url": live_url,
        "content_hash": content_hash,
        "published_at": now.isoformat(),
        "was_unchanged": False,
    }
