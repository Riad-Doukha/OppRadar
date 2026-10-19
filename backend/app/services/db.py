"""Supabase client factory.

Uses the service-role key on the server only — never ship it to the browser.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_db() -> Client | None:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return None  # not configured yet (e.g. local tests)
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
