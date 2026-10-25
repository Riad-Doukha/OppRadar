# Gmail delivery: the RFC 822 message we hand to the Gmail API, the token
# refresh, and the Supabase "Send Email" hook (signature, language, links).

import base64
import email
import hashlib
import hmac
import json
import time
from email import policy

import pytest

from app.config import get_settings
from app.services import gmail, mailer

SECRET_BYTES = b"0123456789abcdef0123456789abcdef"
SECRET = "v1,whsec_" + base64.b64encode(SECRET_BYTES).decode()


@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    for key, value in {
        "gmail_client_id": "cid",
        "gmail_client_secret": "csecret",
        "gmail_refresh_token": "refresh",
        "mail_from": "OppRadar <oppradar.team@gmail.com>",
        "supabase_email_hook_secret": SECRET,
        "app_url": "https://oppradar.example",
    }.items():
        monkeypatch.setattr(s, key, value)
    return s


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(
        mailer,
        "send",
        lambda to, subject, html, user_id=None: sent.append((to, subject, html)) or True,
    )
    return sent


def test_message_has_html_text_and_headers():
    raw = gmail.build(
        "OppRadar <team@gmail.com>",
        "student@example.com",
        "Nouvelle correspondance : é",
        '<p>Hi</p><a href="https://x.dz/o/1">Open</a>',
        {"List-Unsubscribe": "<https://api.x/unsub>"},
    )
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
    assert msg["From"] == "OppRadar <team@gmail.com>" and msg["To"] == "student@example.com"
    assert msg["Subject"] == "Nouvelle correspondance : é"
    assert msg["List-Unsubscribe"] == "<https://api.x/unsub>"
    types = [part.get_content_type() for part in msg.walk()]
    assert "text/plain" in types and "text/html" in types
    text = next(p for p in msg.walk() if p.get_content_type() == "text/plain").get_content()
    assert "Open: https://x.dz/o/1" in text


def test_send_refreshes_the_token_and_retries_once(settings, monkeypatch):
    calls = []

    class Resp:
        def __init__(self, status, body=None):
            self.status_code, self._body = status, body or {}

        def json(self):
            return self._body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise gmail.httpx.HTTPStatusError("x", request=None, response=None)

    def post(url, **kw):
        calls.append(url)
        if url == gmail.TOKEN_URL:
            return Resp(200, {"access_token": f"tok{len(calls)}", "expires_in": 3600})
        return Resp(401 if calls.count(gmail.SEND_URL) == 1 else 200)

    monkeypatch.setattr(gmail.httpx, "post", post)
    monkeypatch.setattr(gmail, "_token", {"value": "", "expires": 0.0})
    gmail.send(settings.mail_from, "a@b.dz", "Hi", "<p>Hi</p>", {})
    assert calls == [gmail.TOKEN_URL, gmail.SEND_URL, gmail.TOKEN_URL, gmail.SEND_URL]


def test_mailer_uses_gmail_with_unsubscribe_headers(settings, monkeypatch):
    seen = {}
    monkeypatch.setattr(gmail, "send", lambda *a: seen.update(args=a))
    assert mailer.send("a@b.dz", "Hi", "<p>Hi</p>", user_id="u1") is True
    assert seen["args"][0] == "OppRadar <oppradar.team@gmail.com>"
    assert "/email/unsubscribe?" in seen["args"][4]["List-Unsubscribe"]


def _signed(payload, stamp=None):
    body = json.dumps(payload).encode()
    stamp = str(int(stamp or time.time()))
    sig = base64.b64encode(
        hmac.new(SECRET_BYTES, f"msg_1.{stamp}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    headers = {"webhook-id": "msg_1", "webhook-timestamp": stamp, "webhook-signature": f"v1,{sig}",
               "content-type": "application/json"}  # fmt: skip
    return body, headers


SIGNUP = {
    "user": {"email": "amine@example.dz", "user_metadata": {"locale": "fr"}},
    "email_data": {"email_action_type": "signup", "token_hash": "abc123", "token": "123456",
                   "redirect_to": "https://oppradar.example/auth/callback?next=/onboarding"},
}  # fmt: skip


def test_signup_confirmation_is_sent_in_the_users_language(client, settings, outbox):
    body, headers = _signed(SIGNUP)
    r = client.post("/email/auth-hook", content=body, headers=headers)
    assert r.status_code == 200 and r.json() == {}
    to, subject, html = outbox[0]
    assert to == "amine@example.dz" and subject == "Confirmez votre compte OppRadar"
    link = "https://oppradar.example/auth/callback?token_hash=abc123&amp;type=signup&amp;next="
    assert link + "%2Fonboarding" in html


def test_hook_refuses_bad_or_stale_signatures(client, settings, outbox):
    body, headers = _signed(SIGNUP)
    bad = client.post(
        "/email/auth-hook", content=body, headers=headers | {"webhook-signature": "v1,AAAA"}
    )
    body2, old = _signed(SIGNUP, stamp=time.time() - 3600)
    stale = client.post("/email/auth-hook", content=body2, headers=old)
    assert bad.status_code == 401 and stale.status_code == 401 and outbox == []


def test_email_change_goes_to_both_addresses_and_unsafe_next_is_ignored(client, settings, outbox):
    payload = {
        "user": {"email": "old@example.dz", "new_email": "new@example.dz", "user_metadata": {}},
        "email_data": {"email_action_type": "email_change",
                       "token_hash": "for-new", "token_hash_new": "for-old",
                       "redirect_to": "https://oppradar.example/auth/callback?next=//evil.example"},
    }  # fmt: skip
    body, headers = _signed(payload)
    assert client.post("/email/auth-hook", content=body, headers=headers).status_code == 200
    sent = {to: html for to, _, html in outbox}
    assert (
        "token_hash=for-new" in sent["new@example.dz"]
        and "token_hash=for-old" in sent["old@example.dz"]
    )
    assert all("next=%2Fsettings" in html for html in sent.values())


def test_hook_reports_a_gmail_failure(client, settings, monkeypatch):
    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    body, headers = _signed(SIGNUP)
    r = client.post("/email/auth-hook", content=body, headers=headers)
    assert r.status_code == 503 and r.json()["error"]["http_code"] == 503


def test_language_change_is_copied_for_auth_emails(client, auth, repo, user_id):
    assert client.patch("/me/settings", json={"locale": "ar"}, headers=auth).status_code == 200
    assert repo.auth_locales[user_id] == "ar"
