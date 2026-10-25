# Security guards from the STRIDE review (docs/security/stride.md): pasted links
# must be public before the server fetches them, and the rate-limit IP cannot be
# spoofed with a client-supplied X-Forwarded-For entry.

from types import SimpleNamespace

import pytest

from app import netguard, ratelimit
from app.config import get_settings


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/health",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://[::1]/",
        "https://example.org:8443/",
        "file:///etc/passwd",
        "ftp://example.org/",
    ],
)
def test_private_or_odd_urls_are_refused(url):
    assert netguard.is_public_url(url) is False


def test_public_url_is_allowed(monkeypatch):
    resolved = [(None, None, None, "", ("93.184.215.14", 443))]
    monkeypatch.setattr(netguard.socket, "getaddrinfo", lambda *a, **k: resolved)
    assert netguard.is_public_url("https://example.org/call-for-applications") is True


def _request(headers, peer="10.1.1.1"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_client_ip_ignores_spoofed_forwarded_entries(monkeypatch):
    monkeypatch.setattr(get_settings(), "client_ip_header", "x-forwarded-for")
    req = _request({"x-forwarded-for": "1.2.3.4, 203.0.113.9"})
    assert ratelimit.client_ip(req) == "203.0.113.9"  # the proxy's entry, not the client's


def test_client_ip_defaults_to_the_peer(monkeypatch):
    monkeypatch.setattr(get_settings(), "client_ip_header", "")
    assert ratelimit.client_ip(_request({"x-forwarded-for": "1.2.3.4"})) == "10.1.1.1"


def test_long_pdf_is_refused(client, auth):
    import pymupdf

    with pymupdf.open() as doc:
        for _ in range(get_settings().upload_max_pages + 1):
            doc.new_page()
        data = doc.tobytes()
    r = client.post(
        "/documents",
        files={"file": ("cv.pdf", data, "application/pdf")},
        data={"kind": "cv", "consent_ai_processing": "true"},
        headers=auth,
    )
    assert r.status_code == 413 and "pages" in r.json()["detail"]


def test_retention_purge(repo):
    from datetime import datetime, timedelta, timezone

    from app.services import agent

    old = datetime.now(timezone.utc) - timedelta(days=400)
    repo.chat = [
        {"id": "a", "user_id": "u1", "created_at": old},
        {"id": "b", "user_id": "u1", "created_at": datetime.now(timezone.utc)},
    ]
    repo.profiles = {"u1": {"history_retention": "12_months"}, "u2": {"history_retention": "never"}}
    repo.applications = {("u1", "o"): {"user_id": "u1", "updated_at": old},
                         ("u2", "o"): {"user_id": "u2", "updated_at": old}}  # fmt: skip
    assert agent.purge(repo) == (1, 1)
    assert [m["id"] for m in repo.chat] == ["b"] and list(repo.applications) == [("u2", "o")]


def test_client_ip_check_is_admin_only(client, auth):
    from test_agent_pipeline import ADMIN

    assert client.get("/admin/client-ip", headers=auth).status_code == 403
    r = client.get("/admin/client-ip", headers=ADMIN | {"X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 200 and r.json()["headers"] == {"x-forwarded-for": "1.2.3.4"}
    assert r.json()["used"] == r.json()["peer"]  # header ignored until configured
