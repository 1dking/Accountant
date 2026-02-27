
import logging

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_service: "EncryptionService | None" = None


class EncryptionService:
    """Fernet-based symmetric encryption for secrets stored in the database."""

    def __init__(self, key: str) -> None:
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


def init_encryption_service(key: str) -> EncryptionService:
    global _service
    if not key:
        key = Fernet.generate_key().decode()
        logger.warning(
            "No FERNET_KEY set in .env. Generated ephemeral key — "
            "encrypted data will be lost on restart. Set FERNET_KEY for persistence."
        )
    _service = EncryptionService(key)
    return _service


def get_encryption_service() -> EncryptionService:
    if _service is None:
        raise RuntimeError("Encryption service not initialized. Call init_encryption_service() first.")
    return _service
