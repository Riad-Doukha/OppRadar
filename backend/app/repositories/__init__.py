"""Persistence: pick the repository implementation from settings."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.repositories.base import CHILD_TABLES, NotFoundError, Repository, Row

__all__ = ["CHILD_TABLES", "NotFoundError", "Repository", "Row", "get_repository"]


@lru_cache
def get_repository() -> Repository:
    """Process-wide repository (FastAPI dependency; tests override it)."""
    settings = get_settings()
    if settings.data_backend == "memory":
        from app.repositories.memory import MemoryRepository

        return MemoryRepository()

    from app.repositories.supabase import SupabaseRepository
    from app.services.db import new_service_client

    if new_service_client() is None:
        raise RuntimeError(
            "Supabase is not configured: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "(or DATA_BACKEND=memory for a throwaway local run)."
        )
    return SupabaseRepository(new_service_client, settings.storage_bucket)
