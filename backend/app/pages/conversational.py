"""Conversational PRD-first page generation pipeline.

Workflow (Tempo Labs / Lovable-style):

  1. User opens "New Page" → frontend creates a session (POST /sessions)
  2. User submits prompt → hybrid AI (Gemini → Claude → static)
     produces a structured PRD + sitemap. User can iterate by
     submitting more prompts; each appends to prompt_history and
     re-derives the PRD.
  3. User clicks Approve → session.status='approved'
  4. Frontend triggers generation → background worker walks the
     sitemap, calls the hybrid stack per section for JSX/Tailwind
  5. Worker writes a new Page row with sections_json populated +
     session.status='complete' + session.page_id set
  6. Refining a section later: re-prompts the hybrid stack with the
     section content and the user's instruction.

Provider strategy (Pages v2 — Gemini-first hybrid):
- Gemini 2.5 Pro for PRD generation (better reasoning + JSON output)
- Gemini 2.5 Flash for per-section JSX (fast + cheap, well-defined)
- Claude Sonnet 4.5 / Haiku 4.5 as automatic fallback on Gemini failure
- Hand-written static template as final fallback if both providers fail
- Every call logs the provider actually used (provider= field) so we
  can evaluate Gemini's real-world reliability later.

Privacy / safety: prompts + outputs are logged at INFO level for
observability. PRD/section content is treated as user-authored;
no sanitization is performed at storage time (the static-HTML
compiler handles XSS at render time).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.pages.models import Page, PageGenerationSession, PageStatus

logger = logging.getLogger(__name__)

# Claude — fallback provider
PRD_MODEL = "claude-sonnet-4-5-20250929"
SECTION_MODEL = "claude-haiku-4-5-20251001"
# Token budgets: PRD must fit roughly title + audience + goals (5 short
# strings) + sections array (up to 8 entries × ~150 tokens). Bumped
# 2000 → 4096 after seeing Gemini truncate mid-string at 2000 (which
# manifested as JSONDecodeError "Unterminated string" and forced the
# Claude fallback, which then blew past the proxy timeout → 502).
PRD_MAX_TOKENS = 4096
SECTION_MAX_TOKENS = 1500
# Per-provider HTTP timeouts. Total worst-case round trip is
# (gemini timeout) + (claude timeout) + static — must stay under the
# reverse proxy's read timeout. DreamHost's default is around 60s.
PRD_TIMEOUT_SECONDS = 20.0
SECTION_TIMEOUT_SECONDS = 15.0

# Gemini — primary provider. PRD uses Flash (3-10x faster than Pro for
# our JSON-shaped output) — Pro's extra reasoning isn't worth the 30-60s
# latency. Section gen also uses Flash.
GEMINI_PRD_MODEL = "gemini-2.5-flash"
GEMINI_SECTION_MODEL = "gemini-2.5-flash"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

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

ALWAYS return at least 4 sections. If the user's prompt is short or
vague, make reasonable assumptions and produce a plausible default
page — do not return an empty sections array. The user can iterate
from there.
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
    # max_retries=0: don't let the SDK retry. Each retry adds backoff
    # (0.4s, 0.8s, 1.6s...) that, stacked on top of the Gemini timeout
    # already burned, can push total request time past the proxy's
    # read timeout and produce a 502 even when the call eventually
    # succeeds. Better to fail fast and let the static fallback fire.
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key, max_retries=0,
    )


# ---------------------------------------------------------------------------
# Hybrid provider helpers — Gemini primary, Claude fallback, static fallback.
# ---------------------------------------------------------------------------


def _is_valid_prd(prd: dict | None) -> bool:
    """Shape check for a PRD: must have a title and a non-empty sections
    list whose entries each have id + type + title."""
    if not isinstance(prd, dict):
        return False
    if not isinstance(prd.get("title"), str) or not prd["title"].strip():
        return False
    sections = prd.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    for s in sections:
        if not isinstance(s, dict):
            return False
        if not all(isinstance(s.get(k), str) and s[k] for k in ("id", "type", "title")):
            return False
    return True


def _is_valid_section(s: dict | None) -> bool:
    """Shape check for a generated section: must have jsx_content string."""
    if not isinstance(s, dict):
        return False
    if not isinstance(s.get("jsx_content"), str) or not s["jsx_content"].strip():
        return False
    return True


async def _gemini_call_json(
    api_key: str,
    model: str,
    system_prompt: str,
    user_msg: str,
    max_tokens: int,
    timeout: float,
) -> dict:
    """Call Gemini's REST API with response_mime_type=json. Returns the
    parsed JSON object. Raises on HTTP error, empty response, or JSON
    parse failure so the hybrid wrapper can fall through to Claude."""
    async with httpx.AsyncClient(timeout=timeout) as http:
        resp = await http.post(
            f"{GEMINI_BASE}/{model}:generateContent?key={api_key}",
            json={
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": max_tokens,
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise ValueError("gemini returned empty text")
    return json.loads(_strip_json_fences(text))


async def _claude_call_json(
    settings: Settings,
    model: str,
    system_prompt: str,
    user_msg: str,
    max_tokens: int,
    timeout: float,
) -> dict:
    """Call Claude via the anthropic SDK. Returns the parsed JSON object."""
    client = _client(settings)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
        timeout=timeout,
    )
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )
    return json.loads(_strip_json_fences(raw))


def _static_prd_for(prompt: str) -> dict:
    """Last-resort PRD when both providers fail. Produces a generic
    landing-page skeleton so the user gets *something* and can refine."""
    title = (prompt or "New Page").strip().splitlines()[0][:80] or "New Page"
    return {
        "title": title,
        "audience": "General audience",
        "goals": [
            "Communicate the value proposition",
            "Drive primary conversion",
            "Establish trust",
        ],
        "sections": [
            {"id": "hero", "type": "hero", "title": "Hero",
             "summary": "Opening pitch", "content_brief": prompt[:300] or "Headline + subtitle + CTA"},
            {"id": "features", "type": "features", "title": "Features",
             "summary": "Key benefits", "content_brief": "Three to four core benefits"},
            {"id": "testimonials", "type": "testimonials", "title": "Testimonials",
             "summary": "Social proof", "content_brief": "Two short quotes from users"},
            {"id": "cta", "type": "cta", "title": "Get started",
             "summary": "Primary call to action", "content_brief": "Single bold CTA"},
            {"id": "footer", "type": "footer", "title": "Footer",
             "summary": "Footer links", "content_brief": "Links + copyright"},
        ],
    }


def _static_section_for(brief: dict) -> dict:
    """Last-resort section content. Keeps the page renderable while the
    user iterates via refine."""
    title = brief.get("title") or "Section"
    return {
        "jsx_content": (
            f"<section className=\"py-12 px-6 text-center\">"
            f"<h2 className=\"text-2xl font-bold mb-2\">{title}</h2>"
            f"<p className=\"text-gray-600\">"
            f"{brief.get('summary') or 'Refine this section to add content.'}</p>"
            f"</section>"
        ),
        "metadata": {"static_fallback": True},
    }


async def _generate_prd_hybrid(prompt: str, settings: Settings) -> tuple[dict, str]:
    """Gemini → Claude → static. Returns (prd, provider_label).

    provider_label is one of: "gemini", "claude_fallback", "static_fallback".
    Always succeeds (static fallback is unconditional).
    """
    gemini_key = getattr(settings, "gemini_api_key", "") or ""
    if gemini_key:
        try:
            prd = await _gemini_call_json(
                api_key=gemini_key,
                model=GEMINI_PRD_MODEL,
                system_prompt=PRD_SYSTEM_PROMPT,
                user_msg=prompt,
                max_tokens=PRD_MAX_TOKENS,
                timeout=PRD_TIMEOUT_SECONDS,
            )
            if _is_valid_prd(prd):
                logger.info("pages.prd_provider=gemini")
                return prd, "gemini"
            logger.warning("pages.prd_gemini_invalid_shape keys=%s", list((prd or {}).keys()))
        except Exception as exc:
            logger.warning("pages.prd_gemini_failed err=%s", str(exc)[:200])

    if getattr(settings, "anthropic_api_key", None):
        try:
            prd = await _claude_call_json(
                settings=settings,
                model=PRD_MODEL,
                system_prompt=PRD_SYSTEM_PROMPT,
                user_msg=prompt,
                max_tokens=PRD_MAX_TOKENS,
                timeout=PRD_TIMEOUT_SECONDS,
            )
            if _is_valid_prd(prd):
                logger.info("pages.prd_provider=claude_fallback")
                return prd, "claude_fallback"
            logger.warning("pages.prd_claude_invalid_shape keys=%s", list((prd or {}).keys()))
        except Exception as exc:
            logger.warning("pages.prd_claude_failed err=%s", str(exc)[:200])

    logger.info("pages.prd_provider=static_fallback")
    return _static_prd_for(prompt), "static_fallback"


async def _generate_section_hybrid(
    brief: dict, settings: Settings, *, instruction: str | None = None,
    existing_jsx: str | None = None,
) -> tuple[dict, str]:
    """Gemini → Claude → static for a single section. Returns
    (section_dict, provider_label).

    When instruction + existing_jsx are passed, this is a refine call;
    otherwise it's a fresh-section call.
    """
    if instruction is not None:
        user_msg = (
            f"Refine the existing section based on the user's instruction.\n\n"
            f"Section type: {brief.get('type', 'custom_html')}\n"
            f"Section title: {brief.get('title', '')}\n"
            f"Existing JSX:\n{existing_jsx or ''}\n\n"
            f"User instruction:\n{instruction}\n\n"
            f"Return JSON with the updated jsx_content. Keep the same "
            f"section type; alter content/styling per the instruction."
        )
    else:
        user_msg = (
            f"Section type: {brief.get('type', 'custom_html')}\n"
            f"Section title: {brief.get('title', 'Untitled')}\n\n"
            f"Content brief:\n{brief.get('content_brief') or brief.get('summary') or ''}"
        )

    gemini_key = getattr(settings, "gemini_api_key", "") or ""
    if gemini_key:
        try:
            section = await _gemini_call_json(
                api_key=gemini_key,
                model=GEMINI_SECTION_MODEL,
                system_prompt=SECTION_SYSTEM_PROMPT,
                user_msg=user_msg,
                max_tokens=SECTION_MAX_TOKENS,
                timeout=SECTION_TIMEOUT_SECONDS,
            )
            if _is_valid_section(section):
                logger.info("pages.section_provider=gemini id=%s", brief.get("id"))
                return section, "gemini"
            logger.warning("pages.section_gemini_invalid_shape id=%s", brief.get("id"))
        except Exception as exc:
            logger.warning(
                "pages.section_gemini_failed id=%s err=%s",
                brief.get("id"), str(exc)[:200],
            )

    if getattr(settings, "anthropic_api_key", None):
        try:
            section = await _claude_call_json(
                settings=settings,
                model=SECTION_MODEL,
                system_prompt=SECTION_SYSTEM_PROMPT,
                user_msg=user_msg,
                max_tokens=SECTION_MAX_TOKENS,
                timeout=SECTION_TIMEOUT_SECONDS,
            )
            if _is_valid_section(section):
                logger.info("pages.section_provider=claude_fallback id=%s", brief.get("id"))
                return section, "claude_fallback"
            logger.warning("pages.section_claude_invalid_shape id=%s", brief.get("id"))
        except Exception as exc:
            logger.warning(
                "pages.section_claude_failed id=%s err=%s",
                brief.get("id"), str(exc)[:200],
            )

    logger.info("pages.section_provider=static_fallback id=%s", brief.get("id"))
    return _static_section_for(brief), "static_fallback"


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

    # Hybrid stack handles parse failures + provider outages internally;
    # the static fallback guarantees we return a usable PRD.
    prd, provider = await _generate_prd_hybrid(prompt, settings)
    history.append({
        "role": "assistant",
        "content": json.dumps(prd),
        "timestamp": now,
        "provider": provider,
    })
    sections_list = prd.get("sections") or []
    sitemap = [s.get("id") for s in sections_list if s.get("id")]

    session.prompt_history = history
    session.prd = prd
    session.sitemap = sitemap
    session.error_message = None
    await db.commit()
    await db.refresh(session)
    logger.info(
        "pages.prd_generated session_id=%s sections=%d provider=%s",
        session_id, len(sections_list), provider,
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


async def generate_page_task(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory,
) -> None:
    """Background worker — walk the sitemap, run the hybrid section
    generator per section, persist a new Page row populated with
    sections_json.

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

            generated_sections = []
            for brief in sections_brief:
                # Hybrid stack guarantees a section dict back; static
                # fallback fires if both providers fail or shapes fail.
                generated, provider = await _generate_section_hybrid(brief, settings)
                generated_sections.append({
                    "id": brief.get("id"),
                    "type": brief.get("type"),
                    "title": brief.get("title"),
                    "summary": brief.get("summary"),
                    "jsx_content": generated.get("jsx_content", ""),
                    "metadata": {
                        **(generated.get("metadata") or {}),
                        "provider": provider,
                    },
                })

            # Persist as a new Page row. We also compile sections to
            # full HTML5 right here so the Preview tab has something to
            # render immediately — the legacy preview iframe reads from
            # page.html_content. Same compiler the Publish flow uses,
            # so Preview and Publish never disagree.
            from app.pages.compiler import compile_page

            page = Page(
                id=uuid.uuid4(),
                title=prd.get("title") or "Untitled page",
                slug=_slugify(prd.get("title") or "untitled"),
                description=prd.get("audience") or None,
                status=PageStatus.DRAFT,
                sections_json=json.dumps(generated_sections),
                html_content=None,  # set immediately below
                css_content=None,
                generation_session_id=session.id,
                created_by=user_id,
            )
            try:
                page.html_content = compile_page(page, company_settings=None)
            except Exception as exc:
                # Compile failure is non-fatal — the user still has
                # sections_json and can fix via refine. Log and proceed.
                logger.warning(
                    "pages.generate_compile_failed session_id=%s err=%s",
                    session_id, str(exc)[:200],
                )
            db.add(page)
            await db.flush()  # need page.id

            session.page_id = page.id
            session.status = "complete"
            await db.commit()
            logger.info(
                "pages.generate_complete session_id=%s page_id=%s sections=%d compiled=%s",
                session_id, page.id, len(generated_sections),
                bool(page.html_content),
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
    refined, provider = await _generate_section_hybrid(
        target,
        settings,
        instruction=instruction,
        existing_jsx=target.get("jsx_content", ""),
    )
    target["jsx_content"] = refined.get("jsx_content", target.get("jsx_content"))
    existing_meta = target.get("metadata") or {}
    new_meta = refined.get("metadata") or {}
    target["metadata"] = {**existing_meta, **new_meta, "provider": provider}
    sections[section_index] = target

    page.sections_json = json.dumps(sections)
    # Recompile html_content so the Preview reflects the refined
    # section. compile_page is fast (no AI, pure string ops); we keep
    # it inline. Compile failure stays non-fatal — sections_json is
    # still authoritative and the user can re-refine.
    try:
        from app.pages.compiler import compile_page
        page.html_content = compile_page(page, company_settings=None)
    except Exception as exc:
        logger.warning(
            "pages.section_refine_compile_failed page_id=%s err=%s",
            page_id, str(exc)[:200],
        )
    await db.commit()
    await db.refresh(page)
    logger.info(
        "pages.section_refined page_id=%s index=%d provider=%s",
        page_id, section_index, provider,
    )
    return page
