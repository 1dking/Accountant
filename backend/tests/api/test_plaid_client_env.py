"""Regression: the Plaid client must build for every environment string.

Newer plaid-python SDKs removed the deprecated `Development` environment. The
env map referenced `plaid.Environment.Development` unconditionally, so
`_get_plaid_client` raised AttributeError for EVERY environment (sandbox and
production alike) — the Connect flow failed with "Could not start the bank
connection" no matter what keys were configured.
"""
from types import SimpleNamespace

from app.integrations.plaid.service import _get_plaid_client


def _settings(env: str):
    return SimpleNamespace(plaid_env=env, plaid_client_id="cid", plaid_secret="sek")


def test_plaid_client_builds_for_sandbox_and_production():
    for env in ("sandbox", "production"):
        assert _get_plaid_client(_settings(env)) is not None


def test_plaid_client_tolerates_deprecated_and_unknown_env():
    # 'development' (deprecated/removed) and unknown values must fall back to
    # Sandbox, not crash while building the map.
    for env in ("development", "bogus", ""):
        assert _get_plaid_client(_settings(env)) is not None


def test_country_codes_include_canada_by_parsing():
    from app.integrations.plaid.service import _plaid_country_codes

    codes = _plaid_country_codes(SimpleNamespace(plaid_country_codes="US,CA"))
    assert [c.value for c in codes] == ["US", "CA"]
    # whitespace / case tolerant
    codes = _plaid_country_codes(SimpleNamespace(plaid_country_codes=" us , ca "))
    assert [c.value for c in codes] == ["US", "CA"]
    # empty -> safe fallback so Link always has a country
    assert [c.value for c in _plaid_country_codes(SimpleNamespace(plaid_country_codes=""))] == ["US"]


async def test_link_token_passes_customization_name_when_set(monkeypatch):
    from app.integrations.plaid import service

    captured = {}

    class FakeClient:
        def link_token_create(self, req):
            captured["req"] = req
            return {"link_token": "tok"}

    monkeypatch.setattr(service, "_get_plaid_client", lambda s: FakeClient())
    settings = SimpleNamespace(
        plaid_country_codes="US,CA", plaid_link_customization_name="obrain"
    )
    user = SimpleNamespace(id="00000000-0000-0000-0000-000000000001")

    await service.create_link_token(user, settings)
    assert captured["req"].link_customization_name == "obrain"


async def test_link_token_omits_customization_when_unset(monkeypatch):
    from app.integrations.plaid import service

    captured = {}

    class FakeClient:
        def link_token_create(self, req):
            captured["req"] = req
            return {"link_token": "tok"}

    monkeypatch.setattr(service, "_get_plaid_client", lambda s: FakeClient())
    settings = SimpleNamespace(plaid_country_codes="US,CA", plaid_link_customization_name="")
    user = SimpleNamespace(id="00000000-0000-0000-0000-000000000001")

    await service.create_link_token(user, settings)
    assert not hasattr(captured["req"], "link_customization_name")
