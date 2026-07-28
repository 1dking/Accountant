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
