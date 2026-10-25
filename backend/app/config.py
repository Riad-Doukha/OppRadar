"""Application settings loaded from the environment / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory; the shared .env lives one level up at the repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    # Where the client IP comes from (rate limits). "" = the TCP peer (local);
    # "x-forwarded-for" = its last entry (the one our host's proxy appended);
    # any other name = that single-value header, set by the proxy (never trust
    # a header the proxy does not overwrite: clients can send it themselves).
    client_ip_header: str = ""

    # Persistence: "supabase" in every real deployment; "memory" for tests and
    # for poking at the API without a database (data is lost on restart).
    data_backend: Literal["supabase", "memory"] = "supabase"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # Legacy HS256 projects verify tokens with this secret; when empty the
    # backend verifies against the project's JWKS (asymmetric signing keys).
    supabase_jwt_secret: str = ""
    storage_bucket: str = "documents"

    # Uploads (Figma step 1: "PDF max 5 MB")
    upload_max_mb: int = 5
    upload_max_pages: int = 10  # every page may be OCR'd: bounds the CPU per upload

    # The agent cycle (ingest, then re-match every active agent) on a timer.
    # Off by default: enable it on the one process that should own it.
    agent_scheduler: bool = False
    agent_interval_seconds: int = 3600

    # Email goes out through the Gmail API (scripts/gmail_auth.py makes the token);
    # without these settings emails are only logged. MAIL_FROM must be that Gmail
    # account (or one of its "Send mail as" aliases).
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    mail_from: str = ""  # e.g. "OppRadar <oppradar.team@gmail.com>"
    # Supabase Auth "Send Email" hook secret (v1,whsec_...): auth emails via Gmail too.
    supabase_email_hook_secret: str = ""
    email_secret: str = ""  # signs unsubscribe links (falls back to the JWT secret)
    app_url: str = "http://localhost:3000"  # links in emails
    api_public_url: str = "http://localhost:8000"  # unsubscribe link target

    # Demo account behind "Try the demo instead"
    demo_email: str = "demo@oppradar.app"
    demo_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
