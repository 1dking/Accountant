"""Pages v2 — SectionEditor per-section CRUD.

SectionEditor writes structured edits to sections_json[i].edited_html
(text content) and .style_overrides (typography/color/spacing). It
NEVER appends global CSS rules. These tests verify the four endpoints
that back the editor:

  - PATCH /sections/{idx}    — set edited_html or style_overrides
  - POST  /sections/{idx}/duplicate
  - DELETE /sections/{idx}
  - POST  /sections/{idx}/revert
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User
from app.pages.models import Page, PageStatus
from tests.conftest import auth_header


def _seed_sections() -> list[dict]:
    return [
        {"id": "hero", "type": "hero", "title": "Hero",
         "summary": "Top fold",
         "jsx_content": "<section className=\"py-12\"><h1>Original Hero</h1></section>",
         "metadata": {}},
        {"id": "features", "type": "features", "title": "Features",
         "summary": "Benefits",
         "jsx_content": "<section className=\"py-12\"><h2>Features</h2></section>",
         "metadata": {}},
        {"id": "cta", "type": "cta", "title": "CTA",
         "summary": "Closing",
         "jsx_content": "<section className=\"py-12\"><h2>Get Started</h2></section>",
         "metadata": {}},
    ]


@pytest_asyncio.fixture
async def page(db: AsyncSession, admin_user: User) -> Page:
    p = Page(
        id=uuid.uuid4(),
        title="Test Page",
        slug=f"test-page-{uuid.uuid4().hex[:6]}",
        status=PageStatus.DRAFT,
        sections_json=json.dumps(_seed_sections()),
        html_content="<section>old html</section>",
        created_by=admin_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.high
async def test_patch_section_writes_edited_html_no_global_css(
    client: AsyncClient, admin_user: User, db: AsyncSession, page: Page
):
    """PATCH writes structured edited_html to sections_json[idx].
    css_content stays untouched — the bug that sparked this refactor
    was font-size adjustments appending nth-child !important rules to
    page.css_content. SectionEditor closes that off entirely."""
    css_before = page.css_content
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/0",
        json={"edited_html": "<section className=\"py-12\"><h1 style=\"font-size:64px\">Edited Hero</h1></section>"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    async with factory() as fresh:
        row = await fresh.execute(select(Page).where(Page.id == page.id))
        updated = row.scalar_one()
        sections = json.loads(updated.sections_json)
        assert sections[0]["edited_html"] == (
            "<section className=\"py-12\"><h1 style=\"font-size:64px\">Edited Hero</h1></section>"
        )
        # Indexes 1 and 2 stay byte-for-byte unchanged
        assert "edited_html" not in sections[1]
        assert "edited_html" not in sections[2]
        # css_content NOT clobbered with global rules
        assert updated.css_content == css_before
        # html_content recompiled to reflect the new section content
        assert "Edited Hero" in (updated.html_content or "")


@pytest.mark.high
async def test_patch_section_style_overrides_accepted(
    client: AsyncClient, admin_user: User, page: Page
):
    """PATCH with style_overrides dict persists to sections_json. v1
    of SectionEditor uses inline styles in edited_html for the
    common case; style_overrides is the structured field reserved
    for cross-cutting style changes (theme swaps, future work)."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/1",
        json={"style_overrides": {"h2": {"fontSize": "48px", "color": "#4338ca"}}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert sections[1]["style_overrides"] == {"h2": {"fontSize": "48px", "color": "#4338ca"}}


@pytest.mark.high
async def test_duplicate_section_creates_copy(
    client: AsyncClient, admin_user: User, page: Page
):
    """Duplicate inserts a deep copy at idx+1. Original section
    unchanged; total sections grows by one; copy gets a unique id."""
    resp = await client.post(
        f"/api/pages/{page.id}/sections/0/duplicate",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert len(sections) == 4  # was 3
    assert sections[0]["id"] == "hero"
    assert sections[1]["id"].startswith("hero-copy-")  # the clone
    assert sections[1]["type"] == "hero"
    assert sections[1]["jsx_content"] == sections[0]["jsx_content"]
    # Following sections shifted but otherwise unchanged
    assert sections[2]["id"] == "features"
    assert sections[3]["id"] == "cta"


@pytest.mark.high
async def test_delete_section_removes_from_array(
    client: AsyncClient, admin_user: User, page: Page
):
    """Delete removes section[idx] and shifts the rest. compile_page
    re-runs so html_content drops the deleted section's content too."""
    resp = await client.delete(
        f"/api/pages/{page.id}/sections/1",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert len(sections) == 2
    assert sections[0]["id"] == "hero"
    assert sections[1]["id"] == "cta"  # was at index 2, now at 1
    # html_content no longer contains the deleted features section
    assert "Features" not in (data["html_content"] or "")


@pytest.mark.high
async def test_revert_section_clears_edits(
    client: AsyncClient, admin_user: User, page: Page
):
    """Revert drops edited_html + style_overrides; the next compile
    falls back to jsx_content. jsx_content itself is preserved so
    the AI original is never lost."""
    # First, set some edits
    await client.patch(
        f"/api/pages/{page.id}/sections/0",
        json={
            "edited_html": "<section><h1>USER EDITED</h1></section>",
            "style_overrides": {"h1": {"fontSize": "72px"}},
        },
        headers=auth_header(admin_user),
    )

    # Now revert
    resp = await client.post(
        f"/api/pages/{page.id}/sections/0/revert",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    sections = json.loads(data["sections_json"])
    assert "edited_html" not in sections[0]
    assert "style_overrides" not in sections[0]
    # jsx_content preserved
    assert "Original Hero" in sections[0]["jsx_content"]
    # html_content recompiled from jsx_content (USER EDITED gone)
    assert "USER EDITED" not in (data["html_content"] or "")
    assert "Original Hero" in (data["html_content"] or "")


@pytest.mark.normal
async def test_section_index_out_of_range_returns_400(
    client: AsyncClient, admin_user: User, page: Page
):
    """Out-of-range index returns 400 with the actual section count
    in the message so the UI can surface a useful error."""
    resp = await client.patch(
        f"/api/pages/{page.id}/sections/99",
        json={"edited_html": "<section>oops</section>"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    body = resp.json()
    msg = body["error"]["message"]
    assert "99" in msg
    assert "3 sections" in msg
