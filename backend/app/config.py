from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/accountant.db"

    # Auth
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Storage
    storage_type: str = "local"
    storage_path: str = "./data/documents"
    max_upload_size: int = 104_857_600  # 100 MB default
    recordings_storage_path: str = "./data/recordings"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]

    # AI
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    #: Cheaper model for STRUCTURED EXTRACTION (receipts, bank categorisation,
    #: identity capture). These return a fixed JSON shape from a short prompt
    #: and do not need a frontier model; routing them here is ~3x cheaper.
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    #: Master switch for automatic AI extraction on upload. Previously declared
    #: here and NEVER READ anywhere — now honoured by both upload paths.
    ai_auto_extract: bool = True

    # Encryption
    fernet_key: str = ""

    # Google OAuth (shared by login + Gmail integration)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/gmail/callback"
    google_oauth_redirect_uri: str = "http://localhost:5173/auth/google/callback"

    # Plaid
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_connect_webhook_secret: str = ""

    # SMTP defaults
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Accountant"
    smtp_use_tls: bool = True

    # Twilio SMS + Voice
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_kyc_required: bool = False  # V1: bypass KYC for internal use; enable for SaaS launch
    # Telephony rebilling rollout flags — BOTH default OFF so a deploy changes
    # nothing for existing users. Flip once tenants have credit balances and
    # A2P registrations seeded:
    #   telephony_enforce_a2p    -> outbound SMS requires an approved A2P
    #                               10DLC registration (fail-closed carrier rule)
    #   telephony_enforce_credit -> outbound SMS / number purchase require
    #                               prepaid credit (the "never front money" gate)
    # Metering, the ledger, top-ups and the rate card are ALWAYS on — usage is
    # recorded and billed from day one; only the BLOCKING is staged.
    telephony_enforce_a2p: bool = False
    telephony_enforce_credit: bool = False
    #: Comma-separated emails whose accounts bypass telephony enforcement
    #: (A2P + prepaid credit). For operator-owned accounts — same shape as
    #: super_admin_emails. Everyone else is enforced normally.
    telephony_exempt_emails: str = ""
    # Voice (AccessToken-based — distinct from account_sid/auth_token)
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_twiml_app_sid: str = ""

    # GoHighLevel
    ghl_api_key: str = ""
    ghl_location_id: str = ""

    # Public access
    public_base_url: str = "http://localhost:5173"

    # Self-serve signup — when True, anyone can create their own workspace
    # (each signup becomes the ADMIN of their own account). When False,
    # only first-time setup (zero users) is allowed and everyone else must
    # be provisioned by an admin.
    allow_public_registration: bool = True

    # Cloudflare R2 Storage
    cloudflare_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint: str = ""

    # LiveKit (video meetings)
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Hocuspocus (Docs real-time collaboration) -- local-only process,
    # reached through the /api/collaborate WebSocket proxy in main.py since
    # DreamHost's proxy only exposes port 8000.
    hocuspocus_port: int = 1234

    # Gemini AI (page builder)
    gemini_api_key: str = ""

    # Google Calendar sync
    google_calendar_sync_enabled: bool = False
    google_calendar_redirect_uri: str = "http://localhost:8000/api/integrations/google-calendar/callback"

    # VAPID keys for Web Push notifications
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claims_email: str = "mailto:admin@example.com"

    # OpenAI (embeddings + transcription)
    openai_api_key: str = ""

    # AssemblyAI (alternative transcription)
    assemblyai_api_key: str = ""

    # O-Brain settings
    obrain_rate_limit_per_hour: int = 120

    # Platform admin
    super_admin_emails: str = ""  # comma-separated list of super admin emails

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    @property
    def is_production(self) -> bool:
        return not self.is_sqlite

    def validate_secrets(self) -> None:
        """Fail fast if critical secrets are missing in production."""
        if not self.secret_key:
            if self.is_production:
                raise RuntimeError(
                    "SECRET_KEY environment variable must be set in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            # Auto-generate for local dev only
            import secrets as _s
            object.__setattr__(self, "secret_key", _s.token_urlsafe(64))
