"""Gmail API sender (users.messages.send) for every email the app sends.

Auth is OAuth 2.0 with a long-lived refresh token for the sending account
(scope gmail.send only), created once with `python scripts/gmail_auth.py`. The
access token is refreshed here and cached until it expires. Plain httpx: no
Google client library needed.
"""

from __future__ import annotations

import base64
import re
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import httpx

from app.config import get_settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPE = "https://www.googleapis.com/auth/gmail.send"

_lock = threading.Lock()
_token: dict[str, float | str] = {"value": "", "expires": 0.0}


def configured() -> bool:
    s = get_settings()
    return bool(s.gmail_client_id and s.gmail_client_secret and s.gmail_refresh_token)


def _access_token(force: bool = False) -> str:
    with _lock:
        if not force and _token["value"] and time.time() < float(_token["expires"]) - 60:
            return str(_token["value"])
        s = get_settings()
        r = httpx.post(
            TOKEN_URL,
            data={
                "client_id": s.gmail_client_id,
                "client_secret": s.gmail_client_secret,
                "refresh_token": s.gmail_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
        _token.update(
            value=body["access_token"], expires=time.time() + body.get("expires_in", 3600)
        )
        return str(_token["value"])


def _plain(html: str) -> str:
    """Text part for clients that do not show HTML (and for spam filters)."""
    text = re.sub(r"<(br|/p|/li|/h\d)\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2: \1", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build(sender: str, to: str, subject: str, html: str, headers: dict[str, str]) -> str:
    """The RFC 822 message, base64url-encoded as the Gmail API expects."""
    msg = EmailMessage()
    name, addr = parseaddr(sender)
    msg["From"] = formataddr((name, addr)) if name else addr
    msg["To"] = to
    msg["Subject"] = subject
    for key, value in headers.items():
        msg[key] = value
    msg.set_content(_plain(html))
    msg.add_alternative(html, subtype="html")
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send(sender: str, to: str, subject: str, html: str, headers: dict[str, str]) -> None:
    """Send one email; raises httpx.HTTPError when Gmail refuses it."""
    raw = build(sender, to, subject, html, headers)
    for attempt in range(2):
        r = httpx.post(
            SEND_URL,
            json={"raw": raw},
            headers={"Authorization": f"Bearer {_access_token(force=attempt > 0)}"},
            timeout=20,
        )
        if r.status_code != 401:  # 401: token revoked or expired early, refresh once
            break
    r.raise_for_status()
