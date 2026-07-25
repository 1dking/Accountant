"""TOTP (RFC 6238) MFA + recovery codes.

Implemented on the standard library (hmac/hashlib/base64) rather than adding a
dependency like pyotp — it's ~40 lines, avoids a new supply-chain surface, and
avoids a network install on the VPS deploy. Compatible with Google Authenticator,
Authy, 1Password, etc. (SHA1, 6 digits, 30s period).

The TOTP secret is stored ENCRYPTED on the user (Fernet, via the app encryption
service). Recovery codes are stored as SHA-256 hashes only — the plaintext is
shown once at enrollment and never again.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD = 30
ISSUER = "Accountant"

# Number of recovery codes minted at enrollment.
RECOVERY_CODE_COUNT = 10


def generate_secret() -> str:
    """A fresh base32 TOTP secret (160 bits) for a new enrollment."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")


def _hotp(secret_b32: str, counter: int, digits: int = DIGITS) -> str:
    key = base64.b32decode(secret_b32, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        (digest[offset] & 0x7F) << 24
        | (digest[offset + 1] & 0xFF) << 16
        | (digest[offset + 2] & 0xFF) << 8
        | (digest[offset + 3] & 0xFF)
    )
    return str(binary % (10 ** digits)).zfill(digits)


def totp_now(secret_b32: str, at: float | None = None) -> str:
    """The current TOTP code. ``at`` overridable for deterministic tests."""
    if at is None:
        at = time.time()
    return _hotp(secret_b32, int(at // PERIOD))


def verify_totp(secret_b32: str, code: str, at: float | None = None, window: int = 1) -> bool:
    """Constant-time verify with a +/- ``window`` step tolerance for clock skew."""
    if not secret_b32 or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return False
    if at is None:
        at = time.time()
    counter = int(at // PERIOD)
    for w in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret_b32, counter + w), code):
            return True
    return False


def provisioning_uri(secret_b32: str, account_name: str, issuer: str = ISSUER) -> str:
    """otpauth:// URI the frontend renders as a QR code for the authenticator app."""
    label = quote(f"{issuer}:{account_name}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={PERIOD}"
    )


# ---------------------------------------------------------------------------
# Recovery codes
# ---------------------------------------------------------------------------


def _normalize_recovery(code: str) -> str:
    return (code or "").strip().replace("-", "").replace(" ", "").lower()


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(_normalize_recovery(code).encode()).hexdigest()


def generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> tuple[list[str], list[str]]:
    """Return (plaintext_codes, hashed_codes).

    Plaintext is shown to the user exactly once; only the hashes are persisted.
    Codes are formatted xxxx-xxxx for readability but normalized on verify.
    """
    plain: list[str] = []
    hashed: list[str] = []
    for _ in range(n):
        raw = secrets.token_hex(4) + secrets.token_hex(4)  # 16 hex chars
        formatted = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}"
        plain.append(formatted)
        hashed.append(hash_recovery_code(formatted))
    return plain, hashed


def consume_recovery_code(code: str, hashed_codes: list[str]) -> list[str] | None:
    """If ``code`` matches an unused hash, return the remaining hashes; else None."""
    target = hash_recovery_code(code)
    for i, h in enumerate(hashed_codes):
        if hmac.compare_digest(h, target):
            return hashed_codes[:i] + hashed_codes[i + 1 :]
    return None
