"""Conversational PRD-first page generation pipeline.

Workflow (Tempo Labs / Lovable-style):

  1. User opens "New Page" → frontend creates a session (POST /sessions)
  2. User submits prompt → Claude Sonnet 4.6 produces a structured
     PRD (title, audience, goals, sections array) + sitemap
     (POST /sessions/{id}/prompt). User can iterate by submitting
     more prompts; each appends to prompt_history and re-derives
     the PRD.
  3. User clicks Approve → session.status='approved'
     (POST /sessions/{id}/approve)
  4. Frontend triggers generation → background worker walks the
     sitemap, calls Claude per section for the JSX/Tailwind content
     (POST /sessions/{id}/generate)
  5. Worker writes a new Page row with sections_json populated +
     session.status='complete' + session.page_id set
  6. Refining a section later: POST /pages/{id}/sections/{idx}/refine
     re-prompts Claude with the section content and the user's
     instruction; replaces just that section's content.

Anthropic Claude Sonnet 4.6 is the model for PRD/sitemap (needs the
better reasoning), Haiku 4.5 for per-section JSX generation (fast +
cheap, the section template is well-defined).

Privacy / safety: prompts + outputs are logged at INFO level for
observability. PRD/section content is treated as user-authored;
no sanitization is performed at storage time (the static-HTML
compiler in Session 2 will handle XSS at render time).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.pages.models import Page, PageGenerationSession, PageStatus

logger = logging.getLogger(__name__)

PRD_MODEL = "claude-sonnet-4-5-20250929"  # Sonnet 4.5 — Sonnet 4.6 wasn't available at build time
SECTION_MODEL = "claude-haiku-4-5-20251001"
PRD_MAX_TOKENS = 2000
SECTION_MAX_TOKENS = 1500
PRD_TIMEOUT_SECONDS = 30.0
SECTION_TIMEOUT_SECONDS = 20.0

PRD_SYSTEM_PROMPT = """\
You are a Product Requirements Document (PRD) writer for a website
generation tool. The user describes the page they want; you reply
with a STRICT JSON object describing the page structure.

Return JSON only. No markdown fences, no prose. Schema:

{
  "title": "page title for browser tab + h1",
  "audience": "1-sentence description of who this page is for",
  "goals": ["3-5 outcomes the page should drive"],
  "sections": [
    {
      "id": "kebab-case-id",
      "type": "one of: header, hero, features, pricing, testimonials, cta, faq, about, contact_form, gallery, stats, team, footer",
      "title": "section heading",
      "summary": "1-sentence description of section purpose",
      "content_brief": "2-3 sentence brief for AI to expand into actual content"
    }
  ]
}

Pick sections that fit the user's intent. Typical landing page is
6-8 sections (header + hero + features + testimonials + pricing +
cta + footer is a solid baseline). Don't pad with sections the
user didn't imply.

If the user's prompt is too vague to write a useful PRD, ask a
clarifying question in the "audience" field and leave "sections"
empty — the frontend will display this back as a question rather
than render an empty page.
"""

SECTION_SYSTEM_PROMPT = """\
You generate a single page section as Tailwind-styled JSX. The user
provides the section type, title, and a content brief. You return a
JSON object:

{
  "jsx_content": "the entire <section>...</section> JSX as a string",
  "metadata": {"headline": "the H2 of this section", "cta_text": "the CTA button text or null"}
}

Constraints:
- JSX must be a single <section className="..."> wrapper
- Use Tailwind classes only (no inline style attributes except for
  one-off dynamic backgrounds)
- Semantic HTML: <h1> only for hero, <h2> for other section heads,
  <h3> for sub-sections
- Mobile-first responsive (sm: / md: / lg: prefixes where useful)
- No JavaScript event handlers (this is render-only static output)
- No external image URLs — use placeholder gradients or solid colors
- Keep total output under 1200 chars to leave room for additional sections

Return JSON only.
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _client(settings: Settings) -> anthropic.AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise ValueError("anthropic_api_key not configured")
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncSession, user_id: uuid.UUID
) -> PageGenerationSession:
    """Open a new conversational generation session. No prompt yet — the
    frontend immediately calls submit_prompt next."""
    session = PageGenerationSession(
        id=uuid.uuid4(),
        user_id=user_id,
        prompt_history=[],
        prd=None,
        sitemap=None,
        status="drafting",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("pages.session_create id=%s user_id=%s", session.id, user_id)
    return session


async def submit_prompt(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    prompt: str,
    settings: Settings,
) -> PageGenerationSession:
    """Append the user's prompt to the conversation, regenerate the PRD
    via Claude Sonnet 4.5. The PRD replaces (not appends) so the user
    can iterate freely without history compounding."""
    rows = await db.execute(
        select(PageGenerationSession).where(
            PageGenerationSession.id == session_id,
            PageGenerationSession.user_id == user_id,
        )
    )
    session = rows.scalar_one_or_none()
    if session is None:
        raise ValueError("Generation session not found")
    if session.status not in {"drafting", "failed"}:
        raise ValueError(
            f"Cannot submit prompt — session is in status '{session.status}'"
        )

    now = datetime.now(timezone.utc).isoformat()
    history = list(session.prompt_history or [])
    history.append({"role": "user", "content": prompt, "timestamp": now})

    client = _client(settings)
    response = await client.messages.create(
        model=PRD_MODEL,
        max_tokens=PRD_MAX_TOKENS,
        system=PRD_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        timeout=PRD_TIMEOUT_SECONDS,
    )
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )
    cleaned = _strip_json_fences(raw)
    try:
        prd = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning(
            "pages.prd_parse_failed session_id=%s err=%s preview=%r",
            session_id, exc, cleaned[:200],
        )
        # Surface the failure as session error_message rather than
        # raising — the frontend should show "Couldn't parse, try
        # rephrasing" rather than 500.
        session.status = "failed"
        session.error_message = f"PRD JSON parse failed: {exc}"
        await db.commit()
        await db.refresh(session)
        return session

    history.append({"role": "assistant", "content": cleaned, "timestamp": now})
    sections_list = prd.get("sections", [])
    sitemap = [s.get("id") for s in sections_list if s.get("id")]

    session.prompt_history = history
    session.prd = prd
    session.sitemap = sitemap
    session.error_message = None
    # Stay 'drafting' so the user can iterate; explicit Approve flips
    # to 'approved'.
    await db.commit()
    await db.refresh(session)
    logger.info(
        "pages.prd_generated session_id=%s sections=%d",
        session_id, len(sections_list),
    )
    return session


async def approve_prd(
    db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> PageGenerationSession:
    """User confirms the PRD. Status flips to 'approved'; the next call
    to generate_page will fire the worker."""
    rows = await db.execute(
        select(PageGenerationSession).where(
            PageGenerationSession.id == session_id,
            PageGenerationSession.user_id == user_id,
        )
    )
    session = rows.scalar_one_or_none()
    if session is None:
        raise ValueError("Generation session not found")
    if session.prd is None or not session.sitemap:
        raise ValueError("Cannot approve — no PRD generated yet")
    session.status = "approved"
    await db.commit()
    await db.refresh(session)
    logger.info("pages.prd_approved session_id=%s", session_id)
    return session


# ---------------------------------------------------------------------------
# Generation worker
# ---------------------------------------------------------------------------


async def _generate_single_section(
    client: anthropic.AsyncAnthropic,
    section_brief: dict,
) -> dict:
    """One Claude Haiku call to produce JSX for a section."""
    user_msg = (
        f"Section type: {section_brief.get('type', 'custom_html')}\n"
        f"Section title: {section_brief.get('title', 'Untitled')}\n\n"
        f"Content brief:\n{section_brief.get('content_brief') or section_brief.get('summary') or ''}"
    )
    response = await client.messages.create(
        model=SECTION_MODEL,
        max_tokens=SECTION_MAX_TOKENS,
        system=SECTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        timeout=SECTION_TIMEOUT_SECONDS,
    )
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )
    cleaned = _strip_json_fences(raw)
    return json.loads(cleaned)


async def generate_page_task(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory,
) -> None:
    """Background worker — walk the sitemap, call Claude per section,
    persist a new Page row populated with sections_json.

    Never raises. On any failure: session.status='failed' +
    error_message populated.
    """
    settings = Settings()
    async with session_factory() as db:
        rows = await db.execute(
            select(PageGenerationSession).where(
                PageGenerationSession.id == session_id
            )
        )
        session = rows.scalar_one_or_none()
        if session is None:
            logger.error("pages.generate_session_missing id=%s", session_id)
            return

        try:
            if session.status != "approved":
                raise ValueError(
                    f"Cannot generate — status is '{session.status}', not 'approved'"
                )
            session.status = "generating"
            await db.commit()

            prd = session.prd or {}
            sections_brief = prd.get("sections", [])
            if not sections_brief:
                raise ValueError("PRD has no sections to generate")

            client = _client(settings)
            generated_sections = []
            for brief in sections_brief:
                try:
                    generated = await _generate_single_section(client, brief)
                except Exception as exc:
                    logger.warning(
                        "pages.section_generate_failed session_id=%s "
                        "section_id=%s err=%s — using placeholder",
                        session_id, brief.get("id"), str(exc)[:200],
                    )
                    # Section-level failure → keep going with a
                    # placeholder so the user still gets a page they
                    # can refine.
                    generated = {
                        "jsx_content": (
                            f"<section className=\"py-12 px-6 text-center\">"
                            f"<h2 className=\"text-2xl font-bold\">"
                            f"{brief.get('title', 'Section')}</h2>"
                            f"<p className=\"text-gray-600 mt-2\">"
                            f"This section couldn't be generated. Click to refine.</p>"
                            f"</section>"
                        ),
                        "metadata": {"placeholder": True},
                    }
                generated_sections.append({
                    "id": brief.get("id"),
                    "type": brief.get("type"),
                    "title": brief.get("title"),
                    "summary": brief.get("summary"),
                    "jsx_content": generated.get("jsx_content", ""),
                    "metadata": generated.get("metadata") or {},
                })

            # Persist as a new Page row.
            page = Page(
                id=uuid.uuid4(),
                title=prd.get("title") or "Untitled page",
                slug=_slugify(prd.get("title") or "untitled"),
                description=prd.get("audience") or None,
                status=PageStatus.DRAFT,
                sections_json=json.dumps(generated_sections),
                html_content=None,  # Compiled in Session 2's static publish flow
                css_content=None,
                generation_session_id=session.id,
                created_by=user_id,
            )
            db.add(page)
            await db.flush()  # need page.id

            session.page_id = page.id
            session.status = "complete"
            await db.commit()
            logger.info(
                "pages.generate_complete session_id=%s page_id=%s sections=%d",
                session_id, page.id, len(generated_sections),
            )
        except Exception as exc:
            logger.exception(
                "pages.generate_failed session_id=%s err=%s",
                session_id, exc,
            )
            try:
                session.status = "failed"
                session.error_message = str(exc)[:1000]
                await db.commit()
            except Exception:
                logger.exception("pages.failure_recording_failed")


def _slugify(text: str) -> str:
    """URL slug from arbitrary text. Lower + replace non-alnum with -."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        text = "page"
    # Add short suffix so distinct pages with similar titles don't collide.
    return f"{text[:60]}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Per-section refine (post-generation)
# ---------------------------------------------------------------------------


async def refine_section(
    db: AsyncSession,
    page_id: uuid.UUID,
    section_index: int,
    instruction: str,
    user_id: uuid.UUID,
    settings: Settings,
) -> Page:
    """Re-prompt Claude for a single section on an existing page.
    Replaces just that section's jsx_content in sections_json.

    section_index is 0-based into the sections list. Raises if the
    page doesn't belong to the user or the index is out of bounds.
    """
    rows = await db.execute(
        select(Page).where(Page.id == page_id, Page.created_by == user_id)
    )
    page = rows.scalar_one_or_none()
    if page is None:
        raise ValueError("Page not found")

    try:
        sections = json.loads(page.sections_json or "[]")
    except json.JSONDecodeError:
        sections = []
    if section_index < 0 or section_index >= len(sections):
        raise ValueError(
            f"section_index {section_index} out of range "
            f"(page has {len(sections)} sections)"
        )

    target = sections[section_index]
    user_msg = (
        f"Refine the existing section based on the user's instruction.\n\n"
        f"Section type: {target.get('type', 'custom_html')}\n"
        f"Section title: {target.get('title', '')}\n"
        f"Existing JSX:\n{target.get('jsx_content', '')}\n\n"
        f"User instruction:\n{instruction}\n\n"
        f"Return JSON with the updated jsx_content. Keep the same "
        f"section type; alter content/styling per the instruction."
    )
    client = _client(settings)
    response = await client.messages.create(
        model=SECTION_MODEL,
        max_tokens=SECTION_MAX_TOKENS,
        system=SECTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        timeout=SECTION_TIMEOUT_SECONDS,
    )
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )
    cleaned = _strip_json_fences(raw)
    refined = json.loads(cleaned)

    target["jsx_content"] = refined.get("jsx_content", target.get("jsx_content"))
    if refined.get("metadata"):
        target["metadata"] = refined["metadata"]
    sections[section_index] = target

    page.sections_json = json.dumps(sections)
    await db.commit()
    await db.refresh(page)
    logger.info(
        "pages.section_refined page_id=%s index=%d",
        page_id, section_index,
    )
    return page
