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

    # SMTP defaults
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Accountant"
    smtp_use_tls: bool = True

    # Twilio SMS
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # GoHighLevel
    ghl_api_key: str = ""
    ghl_location_id: str = ""

    # Public access
    public_base_url: str = "http://localhost:5173"

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
