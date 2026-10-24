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

    # The agent cycle (ingest, then re-match every active agent) on a timer.
    # Off by default: enable it on the one process that should own it.
    agent_scheduler: bool = False
    agent_interval_seconds: int = 3600

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
