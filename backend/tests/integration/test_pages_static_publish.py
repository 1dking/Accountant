"""Pages v2 Session 2 — static publish pipeline.

Compiler + publisher unit-tested in isolation. The R2 upload is
stubbed at the boto3 layer so tests don't hit Cloudflare.
"""
import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.pages.compiler import _jsx_to_html, compile_page
from app.pages.models import Page, PageStatus


@pytest_asyncio.fixture
async def sample_page(db: AsyncSession, admin_user: User) -> Page:
    """A page with two sections in JSX-flavored content. Mimics what
    the conversational worker emits."""
    page = Page(
        id=uuid.uuid4(),
        title="Acme Accounting",
        slug="acme-accounting-abc123",
        description="For Ontario small businesses",
        meta_title=None,
        meta_description=None,
        status=PageStatus.DRAFT,
        sections_json=json.dumps([
            {
                "id": "hero",
                "type": "hero",
                "title": "Hero",
                "jsx_content": (
                    '<section className="bg-blue-50 py-12">'
                    '<h1 className="text-4xl font-bold">Welcome</h1>'
                    '{/* tagline below */}'
                    '<p className="text-gray-600">Tax + bookkeeping for SMBs</p>'
                    '</section>'
                ),
                "metadata": {},
            },
            {
                "id": "cta",
                "type": "cta",
                "title": "Get in touch",
                "jsx_content": (
                    '<section className="py-12 text-center">'
                    '<button className="px-4 py-2 bg-blue-600 text-white">'
                    'Book a call'
                    '</button>'
                    '</section>'
                ),
                "metadata": {},
            },
        ]),
        created_by=admin_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


@pytest.mark.high
async def test_compiler_emits_valid_html5_skeleton(sample_page: Page):
    """compile_page returns a complete HTML5 doc with charset, viewport,
    title, meta description, canonical URL, Tailwind CDN, JSON-LD,
    and the section content concatenated in render order."""
    html = compile_page(
        sample_page,
        company_settings=None,
        public_base_url="https://accountant.ocidm.io",
    )
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in html
    assert "<meta charset=\"utf-8\">" in html
    assert "viewport" in html
    assert "Acme Accounting" in html  # title
    assert "cdn.tailwindcss.com" in html
    assert 'type="application/ld+json"' in html
    # Sections in order: hero before cta
    assert html.index("Welcome") < html.index("Book a call")
    # Canonical URL constructed from public_base_url + slug
    assert "/p/acme-accounting-abc123" in html


@pytest.mark.high
async def test_compiler_normalizes_jsx_to_html(sample_page: Page):
    """className → class, htmlFor → for, JSX block comments stripped.
    Browsers don't understand JSX; this conversion is non-negotiable
    for valid static HTML."""
    html = compile_page(sample_page)
    # className is rewritten to class everywhere
    assert "className=" not in html
    assert 'class="bg-blue-50 py-12"' in html
    # JSX block comments {/* ... */} are stripped, not rendered
    assert "{/*" not in html
    assert "tagline below" not in html  # the comment content


@pytest.mark.high
async def test_compiler_jsonld_schema_org_organization():
    """JSON-LD Organization block parses as valid JSON when extracted
    from the compiled HTML. The @context + @type are required by
    schema.org for SEO to pick it up."""
    import re
    page = Page(
        id=uuid.uuid4(),
        title="Test",
        slug="test-xyz",
        sections_json=json.dumps([
            {"id": "h", "type": "hero", "jsx_content": "<section>hi</section>"}
        ]),
        created_by=uuid.uuid4(),
        status=PageStatus.DRAFT,
    )
    html = compile_page(page, company_settings=None)
    m = re.search(
        r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
        html, re.DOTALL,
    )
    assert m, "JSON-LD block missing"
    schema = json.loads(m.group(1))
    assert schema["@context"] == "https://schema.org"
    assert schema["@type"] == "Organization"
    assert "name" in schema
    assert "url" in schema


@pytest.mark.high
async def test_compiler_jsonld_uses_company_settings_when_present():
    """When CompanySettings populated, the JSON-LD reflects the real
    business name + contact info. Without it, falls back to a
    brand-agnostic 'Organization' schema (still valid)."""
    page = Page(
        id=uuid.uuid4(),
        title="Test",
        slug="test-abc",
        sections_json=json.dumps([
            {"id": "h", "type": "hero", "jsx_content": "<section>hi</section>"}
        ]),
        created_by=uuid.uuid4(),
        status=PageStatus.DRAFT,
    )

    class _FakeCompany:
        company_name = "OCIDM Accounting"
        company_email = "hello@ocidm.io"
        company_phone = "+1-289-555-0199"
        logo_url = "https://accountant.ocidm.io/logo.png"
        address_line1 = "123 Main St"
        city = "Hamilton"
        state = "ON"
        zip_code = "L8P 1A1"
        country = "CA"

    html = compile_page(page, company_settings=_FakeCompany())
    assert "OCIDM Accounting" in html
    assert "hello@ocidm.io" in html
    assert "Hamilton" in html


@pytest.mark.high
async def test_publish_persists_compiled_html_and_status(
    db: AsyncSession, sample_page: Page, monkeypatch
):
    """Publish flow: compile + upload-to-R2 (stubbed) + page row
    updated with compiled_html, compiled_html_r2_key,
    compiled_html_published_at, status=PUBLISHED."""
    from app.pages.publisher import publish_page_static
    from app.config import Settings

    uploaded: list[dict] = []

    async def _stub_upload(settings, key, html):
        uploaded.append({"key": key, "len": len(html)})

    monkeypatch.setattr(
        "app.pages.publisher._upload_html_to_r2", _stub_upload
    )

    s = Settings()
    s.storage_type = "r2"
    s.r2_access_key_id = "stub"  # bypass the local-fallback branch
    s.public_base_url = "https://accountant.ocidm.io"

    result = await publish_page_static(
        db, sample_page.id, sample_page.created_by, s,
    )

    assert result["was_unchanged"] is False
    assert result["r2_key"] == f"pages/{sample_page.slug}/index.html"
    assert result["live_url"] == (
        f"https://accountant.ocidm.io/api/pages/p/{sample_page.slug}"
    )
    assert len(uploaded) == 1
    assert uploaded[0]["key"] == f"pages/{sample_page.slug}/index.html"

    await db.refresh(sample_page)
    assert sample_page.compiled_html is not None
    assert sample_page.compiled_html.startswith("<!DOCTYPE html>")
    assert sample_page.compiled_html_r2_key == result["r2_key"]
    assert sample_page.compiled_html_published_at is not None
    assert sample_page.status == PageStatus.PUBLISHED


@pytest.mark.normal
async def test_publish_skips_upload_when_unchanged(
    db: AsyncSession, sample_page: Page, monkeypatch
):
    """Re-publishing without changes short-circuits the R2 upload.
    Saves money + CDN cache invalidations. The page row's published_at
    timestamp does NOT advance on the no-op publish."""
    from app.pages.publisher import publish_page_static
    from app.config import Settings

    uploaded_count = [0]

    async def _stub_upload(settings, key, html):
        uploaded_count[0] += 1

    monkeypatch.setattr(
        "app.pages.publisher._upload_html_to_r2", _stub_upload
    )

    s = Settings()
    s.storage_type = "r2"
    s.r2_access_key_id = "stub"
    s.public_base_url = "https://accountant.ocidm.io"

    # First publish — uploads
    r1 = await publish_page_static(db, sample_page.id, sample_page.created_by, s)
    assert r1["was_unchanged"] is False
    assert uploaded_count[0] == 1
    first_published_at = r1["published_at"]

    # Second publish — same content, should short-circuit
    r2 = await publish_page_static(db, sample_page.id, sample_page.created_by, s)
    assert r2["was_unchanged"] is True
    assert uploaded_count[0] == 1, "Expected no second upload"
    assert r2["published_at"] == first_published_at


@pytest.mark.normal
async def test_jsx_to_html_handles_all_rewrites():
    """Unit test on the JSX → HTML transform — className, htmlFor,
    tabIndex, and {/* comments */} all handled."""
    src = (
        '<label htmlFor="email" className="block" tabIndex="0">'
        'Email{/* required */}'
        '</label>'
    )
    out = _jsx_to_html(src)
    assert 'for="email"' in out
    assert 'class="block"' in out
    assert 'tabindex="0"' in out
    assert "{/* required */}" not in out
    assert "required" not in out  # comment content stripped
