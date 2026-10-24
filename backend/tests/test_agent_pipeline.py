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
