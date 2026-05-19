"""Pages v2 conversational generation pipeline — state machine +
parse safety + section refinement.

The Claude calls are stubbed so tests don't burn API credits or
require network. We're testing the orchestration:
  - session lifecycle (drafting → approved → generating → complete)
  - PRD JSON parse failure surfaces as session.status='failed' with
    error_message, NOT a 500
  - section regenerate replaces a single section's jsx_content in
    sections_json without disturbing others
  - template library endpoint registered (verifies routing — the
    actual generation is gated on Gemini key + costs)
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User
from app.pages.models import Page, PageGenerationSession, PageStatus
from tests.conftest import auth_header


@pytest.mark.high
async def test_generation_session_create(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """POST /ai/sessions creates a session in drafting state with empty
    history. The frontend immediately submits the first prompt."""
    resp = await client.post(
        "/api/pages/ai/sessions",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "drafting"
    assert data["prompt_history"] == []
    assert data["prd"] is None
    assert data["page_id"] is None


@pytest.mark.high
async def test_prompt_generates_prd(
    client: AsyncClient, admin_user: User, monkeypatch
):
    """Submitting a prompt calls Claude (stubbed), parses the JSON
    response, populates prd + sitemap. Status stays 'drafting' so the
    user can iterate."""

    # Stub the Claude PRD call to return a well-formed PRD.
    async def _fake_create(**kwargs):
        return _MockMessagesResponse(
            text=json.dumps({
                "title": "Acme Accounting",
                "audience": "Small-business owners in Ontario",
                "goals": ["book a discovery call", "build trust", "show pricing"],
                "sections": [
                    {"id": "hero", "type": "hero", "title": "Welcome",
                     "summary": "Top fold", "content_brief": "Bold headline + CTA"},
                    {"id": "features", "type": "features", "title": "What we do",
                     "summary": "3 cards", "content_brief": "Bookkeeping, tax, payroll"},
                ],
            })
        )

    monkeypatch.setattr(
        "anthropic.AsyncAnthropic",
        lambda **kwargs: _MockAnthropicClient(create_fn=_fake_create),
    )

    # Create session
    r1 = await client.post(
        "/api/pages/ai/sessions", headers=auth_header(admin_user)
    )
    session_id = r1.json()["data"]["id"]

    # Submit prompt
    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "Build a landing page for my accounting firm"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["status"] == "drafting"  # iterable
    assert data["prd"]["title"] == "Acme Accounting"
    assert len(data["prd"]["sections"]) == 2
    assert data["sitemap"] == ["hero", "features"]
    # History captured both turns (user + assistant)
    assert len(data["prompt_history"]) == 2
    assert data["prompt_history"][0]["role"] == "user"
    assert data["prompt_history"][1]["role"] == "assistant"


@pytest.mark.high
async def test_prompt_parse_failure_marks_session_failed(
    client: AsyncClient, admin_user: User, monkeypatch
):
    """Claude returns non-JSON → session.status='failed' with
    error_message populated. NOT a 500 — the frontend should show
    "couldn't parse, try rephrasing" rather than an error toast."""
    async def _fake_create(**kwargs):
        return _MockMessagesResponse(text="i love you but no JSON here sorry")

    monkeypatch.setattr(
        "anthropic.AsyncAnthropic",
        lambda **kwargs: _MockAnthropicClient(create_fn=_fake_create),
    )

    r1 = await client.post(
        "/api/pages/ai/sessions", headers=auth_header(admin_user)
    )
    session_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/pages/ai/sessions/{session_id}/prompt",
        json={"prompt": "anything"},
        headers=auth_header(admin_user),
    )
    assert r2.status_code == 200  # endpoint succeeds
    data = r2.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"] and "PRD JSON parse failed" in data["error_message"]


@pytest.mark.high
async def test_section_regenerate_isolated(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    monkeypatch,
):
    """Refining section index 1 of a 3-section page replaces only that
    section's jsx_content. Indexes 0 and 2 stay byte-for-byte unchanged."""
    page = Page(
        id=uuid.uuid4(),
        title="Test Page",
        slug="test-page-abc123",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {"id": "hero", "type": "hero", "title": "H",
             "jsx_content": "<section>ORIGINAL HERO</section>",
             "metadata": {}},
            {"id": "features", "type": "features", "title": "F",
             "jsx_content": "<section>ORIGINAL FEATURES</section>",
             "metadata": {}},
            {"id": "cta", "type": "cta", "title": "C",
             "jsx_content": "<section>ORIGINAL CTA</section>",
             "metadata": {}},
        ]),
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    async def _fake_create(**kwargs):
        return _MockMessagesResponse(
            text=json.dumps({
                "jsx_content": "<section>REFINED FEATURES</section>",
                "metadata": {"headline": "Refined"},
            })
        )

    monkeypatch.setattr(
        "anthropic.AsyncAnthropic",
        lambda **kwargs: _MockAnthropicClient(create_fn=_fake_create),
    )

    resp = await client.post(
        f"/api/pages/{page.id}/sections/1/refine",
        json={"instruction": "Make features more concise"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    # Re-fetch from a fresh session to bypass identity-map cache.
    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    async with factory() as fresh:
        row = await fresh.execute(select(Page).where(Page.id == page.id))
        updated = row.scalar_one()
        sections = json.loads(updated.sections_json)
        assert sections[0]["jsx_content"] == "<section>ORIGINAL HERO</section>"
        assert sections[1]["jsx_content"] == "<section>REFINED FEATURES</section>"
        assert sections[1]["metadata"]["headline"] == "Refined"
        assert sections[2]["jsx_content"] == "<section>ORIGINAL CTA</section>"


@pytest.mark.normal
async def test_template_library_endpoint_registered(app):
    """Sanity — POST /api/pages/templates/generate-library is wired to
    the router. We assert route presence via the OpenAPI app.routes
    walk (same pattern as test_api_route_registration) rather than
    invoking the endpoint, because the actual handler would call
    Gemini if a key is in .env."""
    paths = {
        getattr(r, "path", None): getattr(r, "methods", set())
        for r in app.routes
    }
    target = "/api/pages/templates/generate-library"
    assert target in paths, f"{target} not registered in app.routes"
    assert "POST" in paths[target]


# ---------------------------------------------------------------------------
# Mock helpers — minimal Anthropic client stubs
# ---------------------------------------------------------------------------


class _MockTextBlock:
    type = "text"
    def __init__(self, text: str):
        self.text = text


class _MockMessagesResponse:
    def __init__(self, text: str):
        self.content = [_MockTextBlock(text)]


class _MockMessagesAPI:
    def __init__(self, create_fn):
        self._create_fn = create_fn

    async def create(self, **kwargs):
        return await self._create_fn(**kwargs)


class _MockAnthropicClient:
    def __init__(self, create_fn):
        self.messages = _MockMessagesAPI(create_fn)
