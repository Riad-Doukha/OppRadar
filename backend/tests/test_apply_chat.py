# Applications tracking (Apply assistant + Applications page) and the
# Ask-the-agent fallback (look-ups in OppRadar's own opportunities).

import uuid
from datetime import date, timedelta

import pytest

from app.services import notifications
from conftest import bearer, make_token


@pytest.fixture(autouse=True)
def no_sync_throttle(monkeypatch):
    monkeypatch.setattr(notifications, "SYNC_EVERY_S", 0)


@pytest.fixture
def opps(repo):
    soon = (date.today() + timedelta(days=20)).isoformat()
    repo.upsert_opportunities(
        [
            {"external_id": "ds", "title": "Algiers Data Sprint", "organizer": "Digital Lab",
             "type": "hackathon", "summary": "A datathon on mobility data", "deadline": soon,
             "url": "https://algiersdatasprint.org/apply", "trust_level": "unknown"},
            {"external_id": "sc", "title": "Young Engineers Scholarship", "organizer": "NAE",
             "type": "scholarship", "summary": "For engineering students", "deadline": soon,
             "url": "https://nae-society.org/scholarship", "trust_level": "unknown"},
        ]
    )  # fmt: skip
    return {r["external_id"]: r["id"] for r in repo.opportunities.values()}


def test_record_and_update_an_application(client, auth, opps):
    oid = opps["ds"]
    saved = client.put(
        f"/me/applications/{oid}", json={"reference": "ADS-2026-04871"}, headers=auth
    )
    assert saved.status_code == 200, saved.text
    app = saved.json()
    assert (
        app["status"] == "submitted"
        and app["submitted_at"]
        and app["reference"] == "ADS-2026-04871"
    )
    assert app["opportunity"]["title"] == "Algiers Data Sprint"

    # One notification for the submission, not repeated on later updates.
    client.put(f"/me/applications/{oid}", json={"status": "accepted"}, headers=auth)
    kinds = [n["kind"] for n in client.get("/me/notifications", headers=auth).json()["items"]]
    assert kinds == ["application"]

    [listed] = client.get("/me/applications", headers=auth).json()
    assert listed["status"] == "accepted" and listed["submitted_at"] == app["submitted_at"]
    assert client.get("/me/dashboard", headers=auth).json()["applications"] == 1

    assert client.delete(f"/me/applications/{oid}", headers=auth).status_code == 204
    assert client.get("/me/applications", headers=auth).json() == []


def test_application_validation_and_isolation(client, auth, opps):
    bad = client.put(f"/me/applications/{opps['ds']}", json={"status": "won"}, headers=auth)
    assert bad.status_code == 422
    assert client.put(f"/me/applications/{uuid.uuid4()}", json={}, headers=auth).status_code == 404
    client.put(f"/me/applications/{opps['ds']}", json={}, headers=auth)
    other = bearer(make_token(str(uuid.uuid4())))
    assert client.get("/me/applications", headers=other).json() == []
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert client.put(f"/me/applications/{opps['ds']}", json={}, headers=demo).status_code == 403


def ask(client, auth, message):
    response = client.post("/chat", json={"message": message}, headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


def test_keyword_question_finds_opportunities(client, auth, opps):
    reply = ask(client, auth, "What documents do I need for the Young Engineers scholarship?")
    user, agent = reply["messages"]
    assert user["role"] == "user" and agent["role"] == "assistant"
    assert [o["title"] for o in agent["opportunities"]][0] == "Young Engineers Scholarship"
    assert "ask from its page" in agent["content"]  # points to the grounded AI answer
    assert agent["citations"][0]["url"] == "https://nae-society.org/scholarship"


def test_pasted_link_matches_an_opportunity(client, auth, opps):
    agent = ask(client, auth, "Check this one: https://algiersdatasprint.org/apply?ref=x")[
        "messages"
    ][1]
    assert [o["title"] for o in agent["opportunities"]] == ["Algiers Data Sprint"]

    unknown = ask(client, auth, "https://example.com/some-form")["messages"][1]
    assert unknown["opportunities"] == [] and "can't read example.com" in unknown["content"]


def test_history_only_with_consent(client, auth, opps):
    ask(client, auth, "hackathon")
    history = client.get("/chat/history", headers=auth).json()
    assert history == {"messages": [], "saved": False, "ai_available": False}

    client.patch("/me/onboarding/alerts", json={"consents": {"chat_history": True}}, headers=auth)
    ask(client, auth, "hackathon")
    history = client.get("/chat/history", headers=auth).json()
    assert history["saved"] is True
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["opportunities"][0]["title"] == "Algiers Data Sprint"

    assert client.delete("/chat/history", headers=auth).status_code == 204
    assert client.get("/chat/history", headers=auth).json()["messages"] == []


def test_empty_and_no_match_questions(client, auth, opps):
    assert ask(client, auth, "what is this?")["messages"][1]["opportunities"] == []
    assert "didn't find" in ask(client, auth, "quantum origami")["messages"][1]["content"]
    assert client.post("/chat", json={"message": ""}, headers=auth).status_code == 422


def test_demo_can_ask_but_nothing_is_stored(client, repo, opps):
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert ask(client, demo, "scholarship")["saved"] is False
    assert repo.chat == []
