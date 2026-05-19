"""Pages v2 — Visual editor corruption seatbelt.

The Visual editor previously persisted body.innerHTML after browser
DOM cleanup destroyed nested HTML5 structure inside the editor iframe,
producing html_content payloads that had zero <section> tags despite
the page having 5 structured sections in sections_json. The PUT
endpoint now refuses payloads matching that pattern. These tests
verify the seatbelt fires when it should and stays out of the way
otherwise.
"""
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.models import Page, PageStatus
from tests.conftest import auth_header


@pytest.mark.high
async def test_put_rejects_html_with_no_sections_when_sections_json_populated(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """PUT /api/pages/{id} with html_content that has 0 <section> tags
    is rejected with 422 when sections_json has >0 sections. This is
    the seatbelt that would have caught the Visual editor corruption
    at the persistence boundary."""
    page = Page(
        id=uuid.uuid4(),
        title="Test Page",
        slug="test-seatbelt-page",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {"id": "hero", "type": "hero", "title": "H",
             "jsx_content": "<section>HERO</section>", "metadata": {}},
            {"id": "cta", "type": "cta", "title": "C",
             "jsx_content": "<section>CTA</section>", "metadata": {}},
        ]),
        html_content="<!DOCTYPE html><html><body><section>HERO</section><section>CTA</section></body></html>",
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    # Simulate the corrupted payload the Visual editor was producing:
    # body.innerHTML after browser DOM cleanup of nested HTML5 structure
    # — meta tags + overlay div, but no <section> wrappers.
    corrupted_html = (
        '<meta charset="utf-8"><div id="__editor_overlay"></div>'
        '<h1>Welcome</h1><p>Lost the wrapping section.</p>'
    )
    resp = await client.put(
        f"/api/pages/{page.id}",
        json={"html_content": corrupted_html},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # App wraps HTTPException as {"error": {"message": ..., ...}}.
    msg = body["error"]["message"]
    assert "section" in msg.lower()
    assert "2 structured sections" in msg


@pytest.mark.high
async def test_put_allows_html_with_sections_when_sections_json_populated(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """PUT with html_content containing <section> tags is allowed.
    The seatbelt only fires on the no-section corruption pattern."""
    page = Page(
        id=uuid.uuid4(),
        title="Test Page 2",
        slug="test-seatbelt-page-2",
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {"id": "hero", "type": "hero", "title": "H",
             "jsx_content": "<section>HERO</section>", "metadata": {}},
        ]),
        html_content="<!DOCTYPE html><html><body><section>OLD</section></body></html>",
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    new_html = "<section><h1>Edited hero</h1></section>"
    resp = await client.put(
        f"/api/pages/{page.id}",
        json={"html_content": new_html},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "Edited hero" in data["html_content"]


@pytest.mark.normal
async def test_put_allows_no_section_html_when_sections_json_empty(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """The seatbelt is gated on existing sections_json being populated.
    Legacy v1 pages with no sections_json can still receive arbitrary
    html_content (including <div>-only layouts)."""
    page = Page(
        id=uuid.uuid4(),
        title="Legacy Page",
        slug="test-legacy-page",
        status=PageStatus.DRAFT,
        sections_json=None,
        html_content="<div>old layout</div>",
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    new_html = "<div>new layout, still no section</div>"
    resp = await client.put(
        f"/api/pages/{page.id}",
        json={"html_content": new_html},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
