"""WebAuthn / FIDO2 passkey credentials.

One row per registered authenticator (a user may register several — phone,
laptop, security key). We store ONLY the public key material; the private key
never leaves the authenticator. This is a second factor that sits ALONGSIDE
TOTP (app/auth/mfa.py) — either one satisfies MFA (see app/auth/mfa_common.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: The credential ID, base64url-encoded (portable across SQLite/Postgres and
    #: directly comparable to the browser's PublicKeyCredential.id).
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    #: COSE-encoded public key bytes. Public key ONLY — never a private key.
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    #: Signature counter. Must strictly increase per use (unless the authenticator
    #: reports 0) — a non-increase signals a cloned authenticator.
    sign_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: JSON array of transports the browser reported (e.g. ["internal","hybrid"]).
    transports: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Attestation format reported at registration (e.g. "none", "packed").
    attestation_fmt: Mapped[str | None] = mapped_column(String(50), nullable=True)
    #: User-supplied friendly name ("Nate's iPhone", "YubiKey").
    device_name: Mapped[str] = mapped_column(String(100), default="Passkey", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
