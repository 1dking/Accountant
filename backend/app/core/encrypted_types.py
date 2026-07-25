"""Transparent application-layer encryption for SQLAlchemy columns.

Reuses the SAME Fernet key path as credentials/tokens (app/core/encryption.py) —
no second key system. Encrypt-on-write, decrypt-on-read, so application code and
queries that only read/write the value are unchanged.

Fail-closed contract: encryption/decryption go through ``get_encryption_service``,
which raises if the service isn't initialized (which only happens when the
FERNET_KEY boot guard has already refused to start). That RuntimeError is
deliberately NOT caught here, so a missing key can never cause a silent plaintext
write or read.

Read tolerance: a stored value that is NOT a Fernet token (legacy plaintext from
before this column was encrypted, e.g. during an in-place migration) is returned
as-is and logged, rather than crashing every read of a partially-migrated table.
Only decrypt failures (InvalidToken / malformed base64) are tolerated — never a
missing key.
"""

import logging
from decimal import Decimal, InvalidOperation

from cryptography.fernet import InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.encryption import get_encryption_service

logger = logging.getLogger(__name__)


def _decrypt_tolerant(value: str) -> str:
    """Decrypt, tolerating legacy plaintext. Raises (fails closed) only if the
    encryption service is unavailable — never for a missing key."""
    service = get_encryption_service()  # raises RuntimeError if uninitialised — fail closed
    try:
        return service.decrypt(value)
    except (InvalidToken, ValueError):
        logger.warning(
            "encrypted_types: read a value that is not encrypted — run the at-rest "
            "encryption migration (scripts/plaid_encrypt_at_rest.py / alembic)."
        )
        return value


class EncryptedString(TypeDecorator):
    """Fernet-encrypted text column. Stores ciphertext; returns plaintext str."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_encryption_service().encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _decrypt_tolerant(value)


class EncryptedNumeric(TypeDecorator):
    """Fernet-encrypted numeric column. Stores the ciphertext of the decimal
    string; returns a ``Decimal``. The value is never stored as a number, so it
    cannot be summed/filtered in SQL — see ENCRYPTION_AT_REST.md."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_encryption_service().encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        plain = _decrypt_tolerant(value)
        try:
            return Decimal(plain)
        except (InvalidOperation, TypeError):
            return None
