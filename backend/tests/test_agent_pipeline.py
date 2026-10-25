# The AI pipeline wired into the app (offline: fake LLM + fake embeddings):
# starting the agent scores the profile, the feed shows score + reasons sorted
# best first, expired / fee-asking opportunities are never matched, alerts
# respect the user's threshold, and admins can run + see ingestion.

import uuid

from conftest import bearer, make_token

ADMIN = bearer(make_token(str(uuid.uuid4()), admin=True))
BASE = {
    "organizer": "ENSIA DevClub", "country": "Algeria", "location": "Algiers", "mode": "onsite",
    "summary": "Student hackathon on AI and data science with Python.",
    "eligibility": ["Students in Algeria", "Python"], "url": "example.org/x",
}  # fmt: skip


def publish(client, **fields):
    r = client.post("/admin/opportunities", json={**BASE, **fields}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def complete_profile(client, auth, threshold=50):
    steps = {
        "about": {"full_name": "Amine Benali", "birth_year": 2003, "nationality": "Algerian",
                  "country": "Algeria", "wilaya": "Algiers"},
        "education": {"education_level": "licence", "field_of_study": "Computer Science",
                      "current_year": 3},
        "skills": {"skills": [{"name": n} for n in ("Python", "Data analysis", "Machine learning")],
                   "interests": ["AI", "Data"], "opportunity_types": ["hackathon", "internship"],
                   "preferred_location": "algeria"},
        "goals": {"goal": "I want to join AI hackathons and find a data internship."},
        "alerts": {"email_enabled": True, "threshold": threshold,
                   "consents": {"terms_privacy": True, "agent_matching": True}},
    }  # fmt: skip
    for step, body in steps.items():
        assert client.patch(f"/me/onboarding/{step}", json=body, headers=auth).status_code == 200
    assert client.post("/me/onboarding/complete", headers=auth).status_code == 200


def test_agent_scores_the_feed(client, auth):
    good = publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    publish(client, title="Old Data Hackathon", type="hackathon", deadline="2001-01-01")
    fee = publish(client, title="Paid Hackathon", type="hackathon", deadline="2099-05-01")
    client.patch(f"/admin/opportunities/{fee}", json={"trust_level": "suspicious"}, headers=ADMIN)
    complete_profile(client, auth)

    before = client.get("/me/dashboard", headers=auth).json()
    assert before["matching_available"] is False and before["matched"] == 0

    assert client.post("/me/agent/start", headers=auth).json()["status"] == "running"
    stats = client.get("/me/dashboard", headers=auth).json()
    assert stats["matching_available"] is True and stats["matched"] >= 1 and stats["last_scan_at"]

    feed = client.get("/me/opportunities", headers=auth).json()
    scores = [o["match"]["score"] for o in feed["items"]]
    assert scores == sorted(scores, reverse=True)  # best first
    titles = [o["title"] for o in feed["items"]]
    assert "Old Data Hackathon" not in titles  # expired: hard-filtered out
    top = next(o for o in feed["items"] if o["id"] == good)
    assert 0 <= top["match"]["score"] <= 100 and top["match"]["top_reasons"]
    assert all(c["status"] in ("met", "unmet", "unknown") for c in top["match"]["criteria"])
    detail = client.get(f"/me/opportunities/{good}", headers=auth).json()
    assert detail["match"]["score"] == top["match"]["score"]


def test_scan_now_and_demo(client, auth):
    publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth)
    r = client.post("/me/agent/scan", headers=auth)
    assert r.status_code == 200 and r.json()["scanned"] >= 1
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert client.post("/me/agent/scan", headers=demo).status_code == 200  # read-only, still scored


def test_match_alerts_respect_the_threshold(client, auth):
    publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth, threshold=50)
    client.post("/me/agent/start", headers=auth)
    feed = client.get("/me/opportunities", headers=auth).json()["items"]
    notes = client.get("/me/notifications", params={"tab": "matches"}, headers=auth).json()["items"]
    above = {o["id"] for o in feed if o["match"]["score"] >= 50}
    assert {n["opportunity_id"] for n in notes} == above  # only matches over the threshold
    client.post("/me/agent/scan", headers=auth)  # a second scan never alerts twice
    again = client.get("/me/notifications", params={"tab": "matches"}, headers=auth).json()["items"]
    assert len(again) == len(notes)


def test_admin_ingestion_run_is_logged(client, auth):
    assert client.post("/admin/ingest", headers=auth).status_code == 403
    r = client.post("/admin/ingest", headers=ADMIN)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["trigger"] == "manual" and run["finished_at"]
    runs = client.get("/admin/ingest/runs", headers=ADMIN).json()
    assert [x["id"] for x in runs] == [run["id"]]


def test_chat_about_an_opportunity_is_grounded(client, auth):
    oid = publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth)
    r = client.post(
        "/chat", json={"message": "What is the deadline?", "opportunity_id": oid}, headers=auth
    ).json()
    reply = r["messages"][1]
    assert r["ai_available"] is True and reply["role"] == "assistant" and reply["content"]
    assert isinstance(reply["in_source"], bool)
    assert [o["id"] for o in reply["opportunities"]] == [oid]
    # An open question stays a search over OppRadar (cards, no AI grounding needed).
    r = client.post("/chat", json={"message": "hackathon"}, headers=auth).json()
    assert r["ai_available"] is False and r["messages"][1]["opportunities"]


def test_manual_ingestion_has_a_cooldown(client):
    assert client.post("/admin/ingest", headers=ADMIN).status_code == 200
    again = client.post("/admin/ingest", headers=ADMIN)
    assert again.status_code == 429 and "try again" in again.json()["detail"]


def test_alerts_held_in_quiet_hours_then_released(client, auth):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth, threshold=50)
    hour = datetime.now(ZoneInfo("Africa/Algiers")).hour
    quiet = {"quiet_start": f"{hour:02d}:00", "quiet_end": f"{(hour + 1) % 24:02d}:00"}
    assert client.patch("/me/onboarding/alerts", json=quiet, headers=auth).status_code == 200
    client.post("/me/agent/start", headers=auth)
    notes = client.get("/me/notifications", params={"tab": "matches"}, headers=auth).json()["items"]
    assert notes and all(n["status"] == "pending" for n in notes)  # held, but visible

    client.patch("/me/onboarding/alerts", json={"clear_quiet_hours": True}, headers=auth)
    assert client.post("/me/agent/scan", headers=auth).json()["notifications_sent"] == len(notes)
    notes = client.get("/me/notifications", params={"tab": "matches"}, headers=auth).json()["items"]
    assert all(n["status"] == "sent" for n in notes)


def test_ai_chat_has_a_daily_limit(client, auth, monkeypatch):
    from app.services import chat

    monkeypatch.setattr(chat, "AI_ANSWERS_PER_DAY", 1)
    oid = publish(client, title="ENSIA AI Hackathon", type="hackathon", deadline="2099-05-01")
    complete_profile(client, auth)
    body = {"message": "Deadline?", "opportunity_id": oid}
    assert client.post("/chat", json=body, headers=auth).json()["ai_available"] is True
    assert client.post("/chat", json=body, headers=auth).json()["ai_available"] is False


def test_unknown_announcement_is_read_for_review(client, auth, monkeypatch):
    from oppradar_ai.schemas import Opportunity

    from app.services import ai, chat

    monkeypatch.setattr(chat, "is_public_url", lambda url: True)  # no DNS in tests
    seen = {}

    def fake_extract(url=None, text=None):
        seen.update(url=url, text=text)
        return Opportunity(
            title="Oran Climate Datathon", organizer="Green Oran", url="https://x.dz"
        )

    monkeypatch.setattr(ai, "extract_opportunity", fake_extract)
    complete_profile(client, auth)
    reply = client.post("/chat", json={"message": "see greenoran.dz/datathon"}, headers=auth).json()
    msg = reply["messages"][1]
    assert seen["url"] == "https://greenoran.dz/datathon"
    assert (
        msg["extracted"]["title"] == "Oran Climate Datathon"
        and "send it for review" in msg["content"]
    )
