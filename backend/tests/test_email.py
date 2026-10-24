# Email alerts: sent match alerts go out once (one email per batch) in the
# user's language with AI text escaped, never for the demo or with email off;
# the signed unsubscribe link turns email off; the test email works.

import uuid

import pytest
from test_agent_pipeline import ADMIN, complete_profile, publish

from app.services import mailer
from conftest import bearer, make_token


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(
        mailer,
        "send",
        lambda to, subject, html, user_id=None: sent.append((to, subject, html)) or True,
    )
    return sent


def test_match_alerts_are_emailed_once(client, auth, outbox):
    publish(client, title="ENSIA <b>AI</b> Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth, threshold=50)
    client.patch("/me/settings", json={"locale": "fr"}, headers=auth)
    client.patch("/me/onboarding/alerts", json={"clear_quiet_hours": True}, headers=auth)
    client.post("/me/agent/start", headers=auth)
    assert len(outbox) == 1
    to, subject, html = outbox[0]
    assert to == "amine.benali@ensia.edu.dz"
    assert subject.startswith("Nouvelle correspondance")  # French, from the saved locale
    assert "&lt;b&gt;AI&lt;/b&gt;" in html and "<b>AI</b>" not in html  # escaped
    assert "/email/unsubscribe?" in html
    client.post("/me/agent/scan", headers=auth)
    assert len(outbox) == 1  # already emailed


def test_no_email_when_off_or_demo(client, auth, outbox):
    publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth, threshold=50)
    client.patch(
        "/me/onboarding/alerts",
        json={"email_enabled": False, "telegram_enabled": True},
        headers=auth,
    )
    client.post("/me/agent/start", headers=auth)
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    client.post("/me/agent/scan", headers=demo)
    assert outbox == []


def test_unsubscribe_link_turns_email_off(client, auth, user_id):
    complete_profile(client, auth)
    bad = client.get("/email/unsubscribe", params={"u": user_id, "t": "nope"})
    assert bad.status_code == 400
    ok = client.get(
        "/email/unsubscribe", params={"u": user_id, "t": mailer.unsubscribe_token(user_id)}
    )
    assert ok.status_code == 200 and "off" in ok.text
    assert client.get("/me", headers=auth).json()["notifications"]["email_enabled"] is False


def test_test_email(client, auth, outbox):
    complete_profile(client, auth)
    r = client.post("/me/notifications/test-email", headers=auth)
    assert r.status_code == 202 and r.json() == {"sent": True}
    assert outbox[0][1] == "OppRadar test alert"
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert client.post("/me/notifications/test-email", headers=demo).status_code == 403
    assert ADMIN  # (shared helpers imported from the pipeline tests)
