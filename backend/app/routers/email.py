"""Email links that work without logging in (signed)."""

from __future__ import annotations

from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.repositories import Repository, get_repository
from app.services import mailer

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]

PAGE = (
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    '<title>OppRadar</title><body style="font-family:Arial,sans-serif;max-width:480px;margin:15vh auto;'
    'padding:0 16px;color:#1e113e"><p style="font-size:20px;font-weight:bold;color:#8b34ff">OppRadar</p>'
    '<p>{message}</p><p><a href="{app}/settings?tab=notifications" style="color:#6b21d6">{link}</a></p>'
)


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=False)
def unsubscribe(
    repo: Repo, u: Annotated[str, Query(max_length=64)], t: Annotated[str, Query(max_length=64)]
) -> HTMLResponse:
    """One click from an alert email: turns email alerts off (in-app alerts stay)."""
    from app.config import get_settings

    app = escape(get_settings().app_url.rstrip("/"))
    if not mailer.valid_unsubscribe(u, t):
        return HTMLResponse(
            PAGE.format(message="This link is not valid.", app=app, link="Settings"),
            status_code=400,
        )
    repo.update_notification_settings(u, {"email_enabled": False})
    message = "Email alerts are off. You'll still see alerts in the app — turn email back on anytime in Settings."
    return HTMLResponse(PAGE.format(message=message, app=app, link="Notification settings"))
