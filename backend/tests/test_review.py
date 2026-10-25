# Organisation submissions + admin review: submissions stay hidden until an
# admin approves them, the submitter is told either way, and admins can add,
# edit, re-label and delete opportunities. Non-admins can't reach /admin.

import uuid

from conftest import bearer, make_token

SUBMISSION = {
    "title": "Oran Climate Datathon",
    "organizer": "Green Oran Club",
    "type": "datathon",
    "mode": "onsite",
    "location": "Oran",
    "country": "Algeria",
    "deadline": "2099-05-01",
    "eligibility": ["Students in Algeria"],
    "summary": "Two days of climate data challenges.",
    "url": "greenoran.dz/datathon",
    "contact_email": "contact@greenoran.dz",
}


def admin_headers():
    return bearer(make_token(str(uuid.uuid4()), admin=True, email="admin@oppradar.app"))


def submit(client, headers, **overrides):
    return client.post("/me/submissions", json={**SUBMISSION, **overrides}, headers=headers)


def public_ids(client):
    return [o["id"] for o in client.get("/opportunities", params={"limit": 100}).json()["items"]]


def kinds_and_titles(client, headers):
    items = client.get("/me/notifications", headers=headers).json()["items"]
    return [(n["kind"], n["title"]) for n in items]


def test_submission_is_hidden_until_approved(client, auth):
    r = submit(client, auth)
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["review_status"] == "pending" and sub["trust_level"] == "unknown"
    assert sub["added_via"] == "form" and sub["url"] == "https://greenoran.dz/datathon"

    assert sub["id"] not in public_ids(client)
    assert client.get(f"/opportunities/{sub['id']}").status_code == 404
    mine = client.get("/me/submissions", headers=auth).json()
    assert [m["id"] for m in mine] == [sub["id"]]
    assert ("system", "Submission received — Oran Climate Datathon") in kinds_and_titles(
        client, auth
    )


def test_submission_rules(client, auth):
    assert client.post("/me/submissions", json=SUBMISSION).status_code == 401
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert submit(client, demo).status_code == 403
    assert submit(client, auth, url="not a url at all").status_code == 422
    assert submit(client, auth, contact_email="nope").status_code == 422
    assert submit(client, auth, trust_level="verified").status_code == 422  # can't self-verify
    for _ in range(5):
        assert submit(client, auth).status_code == 201
    r = submit(client, auth)
    assert r.status_code == 429 and "5 submissions" in r.json()["detail"]


def test_admin_only(client, auth):
    for method, path in [
        ("get", "/admin/stats"),
        ("get", "/admin/opportunities"),
        ("post", "/admin/opportunities"),
        ("delete", f"/admin/opportunities/{uuid.uuid4()}"),
    ]:
        assert getattr(client, method)(path, headers=auth).status_code == 403
    assert client.get("/me", headers=auth).json()["is_admin"] is False
    assert client.get("/me", headers=admin_headers()).json()["is_admin"] is True


def test_approve_publishes_and_notifies(client, auth):
    admin = admin_headers()
    sub = submit(client, auth).json()
    assert client.get("/admin/stats", headers=admin).json()["pending"] == 1
    queue = client.get("/admin/opportunities", params={"status": "pending"}, headers=admin).json()
    assert [o["id"] for o in queue["items"]] == [sub["id"]]
    assert queue["items"][0]["contact_email"] == "contact@greenoran.dz"

    r = client.post(
        f"/admin/opportunities/{sub['id']}/review", json={"status": "approved"}, headers=admin
    )
    assert r.status_code == 200, r.text
    assert r.json()["review_status"] == "approved" and r.json()["trust_level"] == "likely_safe"
    assert r.json()["reviewed_at"]
    assert sub["id"] in public_ids(client)
    assert ("system", "Published — Oran Climate Datathon") in kinds_and_titles(client, auth)
    assert client.get("/admin/stats", headers=admin).json() == {
        "pending": 0,
        "flagged": 0,
        "published": 1,
        "rejected": 0,
    }


def test_reject_with_note(client, auth):
    admin = admin_headers()
    sub = submit(client, auth).json()
    note = "The official page doesn't mention this event."
    r = client.post(
        f"/admin/opportunities/{sub['id']}/review",
        json={"status": "rejected", "note": note},
        headers=admin,
    )
    assert r.status_code == 200 and r.json()["review_status"] == "rejected"
    assert sub["id"] not in public_ids(client)
    mine = client.get("/me/submissions", headers=auth).json()[0]
    assert mine["review_status"] == "rejected" and mine["review_note"] == note
    notes = client.get("/me/notifications", headers=auth).json()["items"]
    rejected = next(n for n in notes if n["title"].startswith("Not published"))
    assert rejected["body"] == note and rejected["action_url"] == "/submit"


def test_admin_create_edit_relabel_delete(client, auth):
    admin = admin_headers()
    body = {k: v for k, v in SUBMISSION.items() if k != "contact_email"}
    r = client.post("/admin/opportunities", json=body, headers=admin)
    assert r.status_code == 201, r.text
    opp = r.json()
    assert opp["review_status"] == "approved" and opp["trust_level"] == "likely_safe"
    assert opp["id"] in public_ids(client)

    r = client.patch(
        f"/admin/opportunities/{opp['id']}",
        json={"trust_level": "scam", "deadline": None, "title": None},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited["trust_level"] == "scam" and edited["deadline"] is None
    assert edited["title"] == SUBMISSION["title"]  # required fields can't be blanked
    assert client.get("/admin/stats", headers=admin).json()["flagged"] == 1
    flagged = client.get("/admin/opportunities", params={"trust": "scam"}, headers=admin).json()
    assert flagged["total"] == 1

    # A user saved it and recorded an application: deleting removes those too.
    assert client.put(f"/me/opportunities/{opp['id']}/saved", headers=auth).status_code == 200
    assert client.put(f"/me/applications/{opp['id']}", json={}, headers=auth).status_code == 200
    assert client.get("/me/dashboard", headers=auth).json()["saved"] == 1
    assert client.delete(f"/admin/opportunities/{opp['id']}", headers=admin).status_code == 204
    assert client.get(f"/opportunities/{opp['id']}").status_code == 404
    assert client.get("/me/applications", headers=auth).json() == []
    assert client.get("/me/dashboard", headers=auth).json()["saved"] == 0
    assert client.delete(f"/admin/opportunities/{opp['id']}", headers=admin).status_code == 404


def test_admin_search_and_validation(client, auth):
    admin = admin_headers()
    submit(client, auth)
    submit(client, auth, title="Tlemcen Robotics Cup", type="competition")
    found = client.get("/admin/opportunities", params={"q": "robotics"}, headers=admin).json()
    assert [o["title"] for o in found["items"]] == ["Tlemcen Robotics Cup"]
    sub_id = found["items"][0]["id"]
    bad = client.post(
        f"/admin/opportunities/{sub_id}/review", json={"status": "maybe"}, headers=admin
    )
    assert bad.status_code == 422
    assert client.get(f"/admin/opportunities/{uuid.uuid4()}", headers=admin).status_code == 404
