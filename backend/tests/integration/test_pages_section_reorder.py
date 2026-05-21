"""Pages v2 — PATCH /api/pages/{id}/sections/reorder (Commit 3.6).

Drag-to-reorder is implemented as a single-move endpoint (not full-
array overwrite) so concurrent edits from elsewhere on the page can't
silently clobber each other. Tests cover the happy paths + boundary
errors + recompile side effect.
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.models import Page, PageStatus
from tests.conftest import auth_header


def _seed_sections() -> list[dict]:
    return [
        {"id": "s-hero",     "type": "hero",     "title": "Hero",     "jsx_content": "<section>HERO</section>",     "metadata": {}},
        {"id": "s-features", "type": "features", "title": "Features", "jsx_content": "<section>FEATURES</section>", "metadata": {}},
        {"id": "s-pricing",  "type": "pricing",  "title": "Pricing",  "jsx_content": "<section>PRICING</section>",  "metadata": {}},
        {"id": "s-cta",      "type": "cta",      "title": "CTA",      "jsx_content": "<section>CTA</section>",      "metadata": {}},
    ]


@pytest_asyncio.fixture
async def page(db: AsyncSession, admin_user: User) -> Page:
    p = Page(
        id=uuid.uuid4(),
        title="Reorder Test",
        slug=f"reorder-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps(_seed_sections()),
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.high
async def test_reorder_moves_section_from_top_to_bottom(
    client: AsyncClient, admin_user: User, page: Page
):
    """from=0, to=3 moves the hero to the end; other sections shift up
    by one. compile_page reruns so html_content reflects the new order."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 0, "to_index": 3},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    ids = [s["id"] for s in sections]
    assert ids == ["s-features", "s-pricing", "s-cta", "s-hero"]
    # html_content compiled in the new order
    html = data["html_content"] or ""
    assert html.index("FEATURES") < html.index("HERO")


@pytest.mark.high
async def test_reorder_moves_section_from_middle_to_top(
    client: AsyncClient, admin_user: User, page: Page
):
    """from=2 (pricing), to=0 moves pricing to the front."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 2, "to_index": 0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    sections = json.loads(resp.json()["data"]["sections_json"])
    ids = [s["id"] for s in sections]
    assert ids == ["s-pricing", "s-hero", "s-features", "s-cta"]


@pytest.mark.high
async def test_reorder_same_index_is_noop(
    client: AsyncClient, admin_user: User, page: Page
):
    """from==to returns the page unchanged — no error, no compile churn."""
    before = page.sections_json
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 1, "to_index": 1},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    sections = json.loads(resp.json()["data"]["sections_json"])
    assert [s["id"] for s in sections] == [
        s["id"] for s in json.loads(before)
    ]


@pytest.mark.normal
async def test_reorder_out_of_range_returns_400(
    client: AsyncClient, admin_user: User, page: Page
):
    """Negative or out-of-bounds indices return 400 with the actual
    range in the message so the UI can surface a useful error."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 99, "to_index": 0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    msg = resp.json()["error"]["message"]
    assert "99" in msg
    assert "0..3" in msg  # 4 sections, valid range 0..3


@pytest.mark.normal
async def test_reorder_non_integer_indices_returns_400(
    client: AsyncClient, admin_user: User, page: Page
):
    """Body must have from_index + to_index as integers."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": "not a number", "to_index": 0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.normal
async def test_reorder_route_resolves_before_section_index_pattern(
    client: AsyncClient, admin_user: User, page: Page
):
    """Sanity: /sections/reorder must NOT be matched by the
    /sections/{section_index} PATCH (which expects an int). The static
    'reorder' string is registered above the parameterized route."""
    # If misordered, FastAPI would 422 trying to parse 'reorder' as int.
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 0, "to_index": 1},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.normal
async def test_reorder_preserves_section_content(
    client: AsyncClient, admin_user: User, page: Page
):
    """Section content (jsx_content, metadata, etc.) survives the move
    untouched — only positions change."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/reorder",
        json={"from_index": 0, "to_index": 2},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    sections = json.loads(resp.json()["data"]["sections_json"])
    hero = next(s for s in sections if s["id"] == "s-hero")
    assert hero["jsx_content"] == "<section>HERO</section>"
    assert hero["type"] == "hero"
