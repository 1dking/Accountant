
import hashlib
import logging
import os
import sys

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_service: "EncryptionService | None" = None

#: Explicit opt-in for a throwaway key. Local dev ONLY. When set, a missing
#: FERNET_KEY yields an ephemeral key (data does not survive restart) instead of
#: refusing to boot. Never set this in production.
_ALLOW_EPHEMERAL_ENV = "ALLOW_EPHEMERAL_FERNET_KEY"


class EncryptionService:
    """Fernet-based symmetric encryption for secrets stored in the database."""

    def __init__(self, key: str) -> None:
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


def _is_test_environment() -> bool:
    """True when running under pytest.

    Test modules call ``init_encryption_service(TEST_SETTINGS.fernet_key)`` with
    an empty key and rely on an ephemeral service; the guard below must not fire
    for them. Broken out so tests can monkeypatch it to exercise the production
    fail-fast path.
    """
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


def _ephemeral_allowed() -> bool:
    return os.getenv(_ALLOW_EPHEMERAL_ENV, "").strip().lower() in ("1", "true", "yes")


def _key_fingerprint(key: str) -> str:
    """Short, non-reversible fingerprint of the key.

    Lets ops confirm the SAME key is loaded across restarts (the whole point of
    the guard) without ever logging the key itself.
    """
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def init_encryption_service(key: str) -> EncryptionService:
    """Initialise the process-wide encryption service.

    Fail-fast contract (URGENT 0a): a missing FERNET_KEY previously fell through
    to an ephemeral key on every backend EXCEPT Postgres. On SQLite — which is
    what production runs — that silently regenerated the key on each restart and
    permanently corrupted every encrypted field (Plaid access tokens, Twilio
    tokens, Gmail/Calendar OAuth tokens, provider credentials). This now refuses
    to boot when the key is absent, regardless of the database backend. The only
    exceptions are the test suite and an explicit local-dev opt-in
    (``ALLOW_EPHEMERAL_FERNET_KEY``).
    """
    global _service

    if key:
        _service = EncryptionService(key)
        # Documented startup confirmation. Never logs the key — only a short
        # fingerprint so a changed key is visible across restarts.
        logger.info(
            "Encryption service initialized with a persistent FERNET_KEY "
            "(fingerprint=%s). Encrypted fields will survive restarts.",
            _key_fingerprint(key),
        )
        return _service

    # No key provided from here down.
    if _is_test_environment():
        key = Fernet.generate_key().decode()
        _service = EncryptionService(key)
        logger.warning("Using ephemeral encryption key (test environment).")
        return _service

    if _ephemeral_allowed():
        key = Fernet.generate_key().decode()
        _service = EncryptionService(key)
        logger.warning(
            "FERNET_KEY is unset and %s is enabled — using an EPHEMERAL key. "
            "Encrypted data will be LOST on the next restart. This is for local "
            "development ONLY; never enable it in production.",
            _ALLOW_EPHEMERAL_ENV,
        )
        return _service

    raise RuntimeError(
        "FERNET_KEY is not set. Refusing to boot: without a persistent key the "
        "app would generate a throwaway key that changes on every restart and "
        "PERMANENTLY corrupt all encrypted fields (Plaid, Twilio, OAuth tokens, "
        "provider credentials). Set FERNET_KEY to a stable value. Generate one "
        "with:\n"
        "  python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"\n"
        f"For local development only, set {_ALLOW_EPHEMERAL_ENV}=1 to accept a "
        "throwaway key."
    )


def get_encryption_service() -> EncryptionService:
    if _service is None:
        raise RuntimeError("Encryption service not initialized. Call init_encryption_service() first.")
    return _service
