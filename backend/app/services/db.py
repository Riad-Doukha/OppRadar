"""Supabase client factories.

Uses the service-role key on the server only — never ship it to the browser.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


def new_service_client() -> Client | None:
    """A fresh service-role client (bypasses RLS). The repository keeps one
    per thread; see SupabaseRepository.db."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return None  # not configured yet (e.g. local tests)
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache
def get_db() -> Client | None:
    """Shared service-role client for single-threaded scripts (seed.py)."""
    return new_service_client()


def get_anon_client() -> Client | None:
    """A fresh anon-key client for signing a user in server-side (demo login).

    Not cached: signing in stores the session on the client instance.
    """
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        return None
    return create_client(settings.supabase_url, settings.supabase_anon_key)
