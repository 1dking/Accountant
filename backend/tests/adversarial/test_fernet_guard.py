"""URGENT 0a — the FERNET_KEY fail-fast guard.

The bug this prevents: on SQLite (production) with FERNET_KEY unset, the app used
to silently generate a throwaway key that changed every restart, permanently
corrupting all encrypted fields. The guard must refuse to boot in that case —
regardless of database backend — while still allowing tests + explicit local dev.
"""

import logging

import pytest
from cryptography.fernet import Fernet

import app.core.encryption as enc


def test_missing_key_refuses_to_boot_in_production(monkeypatch):
    # Force the non-test path and ensure the dev opt-in is not set.
    monkeypatch.setattr(enc, "_is_test_environment", lambda: False)
    monkeypatch.delenv(enc._ALLOW_EPHEMERAL_ENV, raising=False)

    with pytest.raises(RuntimeError) as exc:
        enc.init_encryption_service("")
    assert "FERNET_KEY" in str(exc.value)


def test_missing_key_allowed_with_explicit_dev_optin(monkeypatch):
    monkeypatch.setattr(enc, "_is_test_environment", lambda: False)
    monkeypatch.setenv(enc._ALLOW_EPHEMERAL_ENV, "1")

    service = enc.init_encryption_service("")  # must NOT raise
    token = service.encrypt("hello")
    assert service.decrypt(token) == "hello"


def test_missing_key_allowed_in_test_environment(monkeypatch):
    # Default: we are under pytest, so the ephemeral path is allowed.
    monkeypatch.delenv(enc._ALLOW_EPHEMERAL_ENV, raising=False)
    service = enc.init_encryption_service("")  # must NOT raise
    assert service.decrypt(service.encrypt("x")) == "x"


def test_persistent_key_logs_confirmation_without_leaking_key(monkeypatch, caplog):
    key = Fernet.generate_key().decode()
    with caplog.at_level(logging.INFO, logger="app.core.encryption"):
        enc.init_encryption_service(key)

    text = caplog.text
    assert "persistent FERNET_KEY" in text
    # The raw key must never appear in logs — only the fingerprint.
    assert key not in text
    assert enc._key_fingerprint(key) in text
