"""Bug 4 regression — page_size cap on /api/contacts.

The dialer Contacts tab + Recents tab + Command Palette all used to
send page_size=200, which the backend pagination validator rejected
with 422. The frontend silently rendered an empty state. This test
pins the boundary so a future cap change is loud.
"""
import pytest
from httpx import AsyncClient

from app.auth.models import User
from tests.conftest import auth_header


@pytest.mark.high
async def test_contacts_page_size_at_cap_succeeds(
    client: AsyncClient, admin_user: User
):
    """page_size=100 (the documented maximum) must return 200."""
    resp = await client.get(
        "/api/contacts?page_size=100",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.high
async def test_contacts_page_size_over_cap_returns_422(
    client: AsyncClient, admin_user: User
):
    """page_size=101 must return 422 (validator catches it). The
    dialer used to send 200; this test ensures the boundary stays
    where the dialer expects it."""
    resp = await client.get(
        "/api/contacts?page_size=101",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.normal
async def test_contacts_page_size_default_is_25(
    client: AsyncClient, admin_user: User
):
    """Sanity check on the default. Frontend code that omits page_size
    gets 25 items per page — matches what the pagination helper
    advertises."""
    resp = await client.get("/api/contacts", headers=auth_header(admin_user))
    assert resp.status_code == 200
    meta = resp.json().get("meta") or {}
    assert meta.get("page_size") == 25
