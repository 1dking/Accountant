"""Legal versioning endpoint + Plaid link-config wiring."""

import pytest

from app.core import legal


@pytest.mark.asyncio
async def test_legal_versions_public(client):
    r = await client.get("/api/legal/versions")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["privacy_policy_version"] == legal.PRIVACY_POLICY_VERSION
    assert data["terms_version"] == legal.TERMS_VERSION
    assert data["plaid_consent_version"] == legal.PLAID_CONSENT_VERSION


def test_consent_text_states_required_disclosures():
    """The consent copy must say what is collected, how it's used, and that it
    isn't sold — the Schedule 1 conspicuousness requirement."""
    text = legal.PLAID_CONSENT_TEXT.lower()
    assert "transaction" in text          # what is collected
    assert "bookkeeping" in text          # how it's used
    assert "not sell" in text             # not sold
