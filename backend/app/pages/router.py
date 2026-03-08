"""FastAPI router for the AI page builder module."""

import json
import math
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.pages import service
from app.pages.schemas import (
    AIChatMessage,
    AIGenerateRequest,
    AIRefineRequest,
    CustomDomainCreate,
    CustomDomainResponse,
    PageCreate,
    PageListItem,
    PagePublishRequest,
    PageResponse,
    PageUpdate,
    PageVersionResponse,
    PageAnalyticsSummary,
    SplitTestCreate,
    SplitTestResponse,
    SplitTestVariationCreate,
    SplitTestVariationResponse,
    TemplateCreate,
    TemplateListItem,
    TemplateResponse,
    TemplateUpdate,
    TrackEventRequest,
    VideoUploadResponse,
    WebsiteCreate,
    WebsiteListItem,
    WebsiteResponse,
    WebsiteUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Static paths first
# ---------------------------------------------------------------------------


@router.get("/style-presets")
async def list_style_presets(
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": list(service.STYLE_PRESETS.values())}


@router.get("/section-templates")
async def list_section_templates(
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"data": service.SECTION_TEMPLATES}


# ---------------------------------------------------------------------------
# Page Templates
# ---------------------------------------------------------------------------


@router.get("/templates")
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    templates = await service.list_templates(db)
    return {"data": [TemplateListItem.model_validate(t) for t in templates]}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    t = await service.get_template(db, template_id)
    return {"data": TemplateResponse.model_validate(t)}


@router.post("/templates", status_code=201)
async def create_template(
    data: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    if data.source_page_id:
        t = await service.create_template_from_page(
            db,
            page_id=data.source_page_id,
            name=data.name,
            description=data.description,
            category_industry=data.category_industry,
            category_type=data.category_type,
            scope=data.scope,
            created_by=current_user.id,
        )
    else:
        t = await service.create_template(
            db,
            name=data.name,
            description=data.description,
            category_industry=data.category_industry,
            category_type=data.category_type,
            html_content=data.html_content,
            css_content=data.css_content,
            metadata_json=data.metadata_json,
            scope=data.scope,
            created_by=current_user.id,
        )
    return {"data": TemplateResponse.model_validate(t)}


@router.put("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    t = await service.update_template(db, template_id, data.model_dump(exclude_none=True))
    return {"data": TemplateResponse.model_validate(t)}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_template(db, template_id)
    return {"data": {"message": "Template deleted"}}


@router.post("/templates/{template_id}/create-page", status_code=201)
async def create_page_from_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    title: str = Query(...),
    website_id: uuid.UUID | None = Query(None),
    org_name: str | None = Query(None),
) -> dict:
    page = await service.create_page_from_template(
        db, template_id, title, current_user,
        website_id=website_id, org_name=org_name,
    )
    return {"data": PageResponse.model_validate(page)}


@router.post("/templates/generate-library", status_code=200)
async def generate_template_library(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
    request: Request,
    replace: bool = Query(False, description="Replace existing templates"),
) -> dict:
    """Admin endpoint: generate 30 premium templates using Gemini + reference designs.

    This is a long-running operation (~2-3 minutes). Each template takes ~3-5 seconds.
    """
    from app.pages.generate_templates import generate_all_templates

    settings = request.app.state.settings
    gemini_key = getattr(settings, "gemini_api_key", "") if settings else ""
    if not gemini_key:
        return {"data": {"error": "Gemini API key not configured in settings"}}

    stats = await generate_all_templates(db, gemini_key, replace_existing=replace)
    return {"data": stats}


# ---------------------------------------------------------------------------
# AI endpoints
# ---------------------------------------------------------------------------


@router.post("/ai/generate", status_code=201)
async def ai_generate(
    data: AIGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    request: Request,
) -> dict:
    settings = request.app.state.settings
    result = await service.ai_generate_page(
        db,
        data.prompt,
        data.style_preset,
        data.primary_color,
        data.font_family,
        data.sections,
        settings=settings,
    )
    return {"data": result}


@router.post("/ai/refine")
async def ai_refine(
    data: AIRefineRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    request: Request,
) -> dict:
    settings = request.app.state.settings
    result = await service.ai_refine_page(
        db,
        data.page_id,
        data.instruction,
        data.section_index,
        settings=settings,
    )
    return {"data": result}


@router.post("/ai/chat")
async def ai_chat(
    data: AIChatMessage,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    request: Request,
) -> dict:
    settings = request.app.state.settings
    result = await service.ai_chat_generate(
        db, data.page_id, data.message, settings=settings,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Websites CRUD
# ---------------------------------------------------------------------------


@router.get("/websites")
async def list_websites(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    items = await service.list_websites(db)
    return {"data": items}


@router.post("/websites", status_code=201)
async def create_website(
    data: WebsiteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    ws = await service.create_website(db, data.name, data.slug, current_user)
    return {"data": WebsiteResponse.model_validate(ws)}


@router.get("/websites/{website_id}")
async def get_website(
    website_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    ws = await service.get_website(db, website_id)
    return {"data": WebsiteResponse.model_validate(ws)}


@router.put("/websites/{website_id}")
async def update_website(
    website_id: uuid.UUID,
    data: WebsiteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    ws = await service.update_website(db, website_id, data)
    return {"data": WebsiteResponse.model_validate(ws)}


@router.delete("/websites/{website_id}")
async def delete_website(
    website_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_website(db, website_id)
    return {"data": {"message": "Website deleted"}}


@router.get("/websites/{website_id}/pages")
async def list_website_pages(
    website_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    pages = await service.get_website_pages(db, website_id)
    return {"data": [PageListItem.model_validate(p) for p in pages]}


# ---------------------------------------------------------------------------
# Pages CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_pages(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    pages, total = await service.list_pages(db, page, page_size)
    return {
        "data": [PageListItem.model_validate(p) for p in pages],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("", status_code=201)
async def create_page(
    data: PageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.create_page(db, data, current_user)
    return {"data": PageResponse.model_validate(page)}


@router.get("/{page_id}")
async def get_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    page = await service.get_page(db, page_id)
    return {"data": PageResponse.model_validate(page)}


@router.put("/{page_id}")
async def update_page(
    page_id: uuid.UUID,
    data: PageUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.update_page(db, page_id, data, current_user)
    return {"data": PageResponse.model_validate(page)}


@router.delete("/{page_id}")
async def delete_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_page(db, page_id)
    return {"data": {"message": "Page deleted"}}


@router.post("/{page_id}/publish")
async def publish_page(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    body: PagePublishRequest | None = None,
) -> dict:
    page = await service.publish_page(db, page_id, current_user)
    return {"data": PageResponse.model_validate(page)}


@router.post("/{page_id}/update-live")
async def update_live(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    """Push draft content to live (for already-published pages)."""
    page = await service.update_live(db, page_id, current_user)
    return {"data": PageResponse.model_validate(page)}


# ---------------------------------------------------------------------------
# Custom Domains
# ---------------------------------------------------------------------------


@router.get("/{page_id}/domains")
async def list_page_domains(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    domains = await service.list_page_domains(db, page_id)
    return {"data": [CustomDomainResponse.model_validate(d) for d in domains]}


@router.post("/{page_id}/domains", status_code=201)
async def add_domain(
    page_id: uuid.UUID,
    data: CustomDomainCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    domain = await service.add_custom_domain(db, page_id, data.domain, current_user.id)
    return {"data": CustomDomainResponse.model_validate(domain)}


@router.post("/domains/{domain_id}/verify")
async def verify_domain(
    domain_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    domain = await service.verify_domain_dns(db, domain_id)
    return {"data": CustomDomainResponse.model_validate(domain)}


@router.delete("/domains/{domain_id}")
async def delete_domain(
    domain_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_custom_domain(db, domain_id)
    return {"data": {"message": "Domain deleted"}}


# ---------------------------------------------------------------------------
# Split Tests
# ---------------------------------------------------------------------------


@router.get("/{page_id}/split-tests")
async def list_page_split_tests(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    tests = await service.list_page_tests(db, page_id)
    return {"data": [SplitTestResponse.model_validate(t) for t in tests]}


@router.post("/{page_id}/split-tests", status_code=201)
async def create_split_test(
    page_id: uuid.UUID,
    data: SplitTestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    test = await service.create_split_test(db, page_id, data.name, current_user.id)
    return {"data": SplitTestResponse.model_validate(test)}


@router.get("/split-tests/{test_id}")
async def get_split_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    test = await service.get_split_test(db, test_id)
    return {"data": SplitTestResponse.model_validate(test)}


@router.post("/split-tests/{test_id}/variations", status_code=201)
async def add_variation(
    test_id: uuid.UUID,
    data: SplitTestVariationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    variation = await service.add_variation(
        db, test_id, data.name, data.html_content, data.css_content, data.traffic_percentage,
    )
    return {"data": SplitTestVariationResponse.model_validate(variation)}


@router.post("/split-tests/{test_id}/duplicate-variation", status_code=201)
async def duplicate_as_variation(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    page_id: uuid.UUID = Query(...),
) -> dict:
    variation = await service.duplicate_as_variation(db, test_id, page_id)
    return {"data": SplitTestVariationResponse.model_validate(variation)}


@router.post("/split-tests/{test_id}/start")
async def start_split_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    test = await service.start_test(db, test_id)
    return {"data": SplitTestResponse.model_validate(test)}


@router.post("/split-tests/{test_id}/pause")
async def pause_split_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    test = await service.pause_test(db, test_id)
    return {"data": SplitTestResponse.model_validate(test)}


@router.post("/split-tests/{test_id}/stop")
async def stop_split_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    test = await service.stop_test(db, test_id)
    return {"data": SplitTestResponse.model_validate(test)}


@router.post("/split-tests/{test_id}/declare-winner")
async def declare_winner(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
    variation_id: uuid.UUID = Query(...),
) -> dict:
    test = await service.declare_winner(db, test_id, variation_id)
    return {"data": SplitTestResponse.model_validate(test)}


# ---------------------------------------------------------------------------
# Video upload
# ---------------------------------------------------------------------------


@router.post("/video/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))] = None,
    request: Request = None,
) -> dict:
    settings = request.app.state.settings
    storage_path = getattr(settings, "storage_path", "./data/documents")
    video_dir = os.path.join(storage_path, "videos")
    os.makedirs(video_dir, exist_ok=True)

    # Save uploaded file
    input_path = os.path.join(video_dir, f"upload_{uuid.uuid4()}{os.path.splitext(file.filename or '')[1]}")
    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    result = await service.process_video(input_path, video_dir)

    # Convert paths to URLs
    base = "/api/pages/video/serve"
    return {
        "data": VideoUploadResponse(
            mp4_url=f"{base}/{os.path.basename(result['mp4_path'])}",
            webm_url=f"{base}/{os.path.basename(result['webm_path'])}",
            poster_url=f"{base}/{os.path.basename(result['poster_path'])}",
            duration_seconds=result["duration_seconds"],
        ).model_dump()
    }


@router.get("/video/serve/{filename}")
async def serve_video(
    filename: str,
    request: Request,
):
    """Serve processed video files."""
    from fastapi.responses import FileResponse

    settings = request.app.state.settings
    storage_path = getattr(settings, "storage_path", "./data/documents")
    video_dir = os.path.join(storage_path, "videos")
    file_path = os.path.join(video_dir, filename)

    if not os.path.exists(file_path):
        return {"error": {"code": "NOT_FOUND", "message": "Video not found"}}

    content_type = "video/mp4"
    if filename.endswith(".webm"):
        content_type = "video/webm"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        content_type = "image/jpeg"

    return FileResponse(file_path, media_type=content_type)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/{page_id}/versions")
async def list_versions(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    versions = await service.list_versions(db, page_id)
    return {"data": [PageVersionResponse.model_validate(v) for v in versions]}


@router.post("/{page_id}/versions/{version_id}/restore")
async def restore_version(
    page_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    page = await service.restore_version(db, page_id, version_id, current_user)
    return {"data": PageResponse.model_validate(page)}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/{page_id}/analytics")
async def get_analytics(
    page_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    days: int = Query(30, ge=1, le=365),
) -> dict:
    data = await service.get_page_analytics(db, page_id, days)
    return {"data": PageAnalyticsSummary(**data)}


# ---------------------------------------------------------------------------
# Analytics tracking (public — no auth)
# ---------------------------------------------------------------------------


analytics_router = APIRouter()


@analytics_router.post("/track")
async def track_event(
    data: TrackEventRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> dict:
    """Public endpoint for analytics tracking beacons."""
    await service.track_event(
        db,
        page_id=data.page_id,
        visitor_id=data.visitor_id,
        session_id=data.session_id,
        event_type=data.event_type,
        event_data=data.event_data,
        referrer=data.referrer,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        user_agent=data.user_agent or request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None,
    )
    return {"data": {"ok": True}}


# ---------------------------------------------------------------------------
# Public page hosting
# ---------------------------------------------------------------------------


@router.get("/public/view/{slug}")
async def view_public_page(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> HTMLResponse:
    page = await service.get_page_by_slug(db, slug)

    # Record view
    await service.record_page_view(
        db,
        page.id,
        visitor_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referrer=request.headers.get("referer"),
    )

    # Get website for shared elements
    website = None
    if page.website_id:
        try:
            website = await service.get_website(db, page.website_id)
        except Exception:
            pass

    # Build tracking scripts
    tracking_head = service.build_tracking_head(page, website)
    tracking_body_start = service.build_tracking_body_start(page, website)
    tracking_body_end = service.build_tracking_body_end(page, website)
    base_url = request.app.state.settings.public_base_url
    analytics_script = service.build_analytics_script(str(page.id), base_url)

    # Global CSS
    global_css = ""
    if website and website.global_css:
        global_css = f"<style>{website.global_css}</style>"

    # Nav and footer
    nav_html = ""
    footer_html = ""
    if website:
        nav_html = website.header_html or ""
        footer_html = website.footer_html or ""

    # Use live content if available, otherwise fall back to draft content
    serve_html = page.live_html_content or page.html_content or ''
    serve_css = page.live_css_content or page.css_content or ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.meta_title or page.title}</title>
    <meta name="description" content="{page.meta_description or page.description or ''}">
    {f'<link rel="icon" href="{page.favicon_url}">' if page.favicon_url else ''}
    <style>{serve_css}</style>
    {global_css}
    {page.custom_head_html or ''}
    {tracking_head}
</head>
<body>
    {tracking_body_start}
    {nav_html}
    {serve_html}
    {footer_html}
    {f'<script>{page.js_content}</script>' if page.js_content else ''}
    {tracking_body_end}
    {analytics_script}
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/public/site/{website_slug}")
async def view_website_homepage(
    website_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> HTMLResponse:
    """Serve a website's homepage."""
    from sqlalchemy import select as sa_select
    from app.pages.models import Website as WS, Page as P, PageStatus as PS

    result = await db.execute(
        sa_select(WS).where(WS.slug == website_slug, WS.is_published == True)
    )
    website = result.scalar_one_or_none()
    if not website:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    # Find homepage
    result = await db.execute(
        sa_select(P).where(
            P.website_id == website.id,
            P.is_homepage == True,
            P.status == PS.PUBLISHED,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        # Fall back to first page
        result = await db.execute(
            sa_select(P).where(P.website_id == website.id, P.status == PS.PUBLISHED)
            .order_by(P.page_order)
            .limit(1)
        )
        page = result.scalar_one_or_none()

    if not page:
        return HTMLResponse("<h1>No pages published</h1>", status_code=404)

    # Reuse single page render
    request.state.override_slug = page.slug
    return await view_public_page(page.slug, db, request)


@router.get("/public/site/{website_slug}/{page_slug}")
async def view_website_page(
    website_slug: str,
    page_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> HTMLResponse:
    """Serve a specific page within a website."""
    from sqlalchemy import select as sa_select
    from app.pages.models import Website as WS, Page as P, PageStatus as PS

    result = await db.execute(
        sa_select(WS).where(WS.slug == website_slug, WS.is_published == True)
    )
    website = result.scalar_one_or_none()
    if not website:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    result = await db.execute(
        sa_select(P).where(
            P.website_id == website.id,
            P.slug == page_slug,
            P.status == PS.PUBLISHED,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        return HTMLResponse("<h1>Page Not Found</h1>", status_code=404)

    return await view_public_page(page.slug, db, request)
