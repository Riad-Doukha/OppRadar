"""Auth helpers that need the server. Sign-up / log-in / reset run in the
browser against Supabase Auth directly; only the demo login lives here because
its password must never reach the browser.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.models import DemoSession
from app.services.db import get_anon_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/demo", response_model=DemoSession)
def demo_login() -> DemoSession:
    """'Try the demo instead': a session for the shared read-only demo account.

    The frontend passes the tokens to `supabase.auth.setSession(...)`.
    """
    settings = get_settings()
    client = get_anon_client()
    if client is None or not settings.demo_password:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The demo is not available right now."
        )
    try:
        response = client.auth.sign_in_with_password(
            {"email": settings.demo_email, "password": settings.demo_password}
        )
    except Exception as exc:  # supabase raises AuthApiError subclasses
        logger.exception("demo login failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The demo is not available right now."
        ) from exc
    session = response.session
    if session is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The demo is not available right now."
        )
    return DemoSession(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )
