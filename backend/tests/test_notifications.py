# In-app notifications: deadline reminders for saved opportunities, weekly
# profile tips, the agent-started message, tabs, read/dismiss, isolation.

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import notifications
from conftest import bearer, make_token


@pytest.fixture(autouse=True)
def no_sync_throttle(monkeypatch):
    monkeypatch.setattr(notifications, "SYNC_EVERY_S", 0)


@pytest.fixture
def opportunities(repo):
    rows = [
        {"external_id": f"t{i}", "title": f"Opportunity {i}", "organizer": "Org",
         "type": "internship", "trust_level": "unknown",
         "deadline": (date.today() + timedelta(days=days)).isoformat()}
        for i, days in enumerate([1, 2, 10])
    ]  # fmt: skip
    repo.upsert_opportunities(rows)
    return {r["external_id"]: r["id"] for r in repo.opportunities.values()}


def listing(client, auth, tab="all"):
    response = client.get("/me/notifications", params={"tab": tab}, headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


def test_starts_empty(client, auth):
    assert listing(client, auth) == {"items": [], "unread": 0}


def test_deadline_reminders_for_saved_opportunities(client, auth, opportunities):
    for key in ("t0", "t2"):  # closes in 1 day / in 10 days
        client.put(f"/me/opportunities/{opportunities[key]}/saved", headers=auth)
    page = listing(client, auth)
    assert page["unread"] == 1
    [item] = page["items"]
    assert item["kind"] == "deadline"
    assert item["title"] == "Closing soon: Opportunity 0 — 1 day left"
    assert item["action_url"] == f"/opportunities/{opportunities['t0']}"
    # Idempotent: listing again creates no duplicate.
    assert len(listing(client, auth)["items"]) == 1
    assert (
        listing(client, auth, "deadlines")["items"]
        and not listing(client, auth, "matches")["items"]
    )


def test_deadline_reminders_respect_the_rule(client, auth, opportunities):
    client.patch("/me/onboarding/alerts", json={"rule_deadline_reminders": False}, headers=auth)
    client.put(f"/me/opportunities/{opportunities['t1']}/saved", headers=auth)
    assert listing(client, auth)["items"] == []


def test_weekly_profile_tip_only_when_enabled_and_incomplete(client, auth, repo, user_id):
    client.get("/me", headers=auth)
    repo.update_profile(
        user_id, {"onboarding_completed_at": datetime.now(timezone.utc), "completeness": 0.6}
    )
    assert listing(client, auth)["items"] == []  # tips are off by default
    client.patch("/me/onboarding/alerts", json={"rule_profile_tips": True}, headers=auth)
    items = listing(client, auth, "system")["items"]
    assert [i["kind"] for i in items] == ["tip"]
    assert "% complete" in items[0]["body"]  # completeness recomputed on save
    assert len(listing(client, auth)["items"]) == 1  # one per week


def test_agent_started_message(client, auth):
    client.post("/me/agent/start", headers=auth)
    [item] = listing(client, auth, "system")["items"]
    assert item["kind"] == "system" and item["title"] == "Your agent is set up"


def test_mark_read_and_dismiss(client, auth, opportunities):
    for key in ("t0", "t1"):
        client.put(f"/me/opportunities/{opportunities[key]}/saved", headers=auth)
    items = listing(client, auth)["items"]
    assert len(items) == 2

    after = client.post(
        "/me/notifications/read", json={"ids": [items[0]["id"]]}, headers=auth
    ).json()
    assert after["unread"] == 1
    assert client.post("/me/notifications/read", json={}, headers=auth).json()["unread"] == 0
    assert all(i["read"] for i in listing(client, auth)["items"])

    assert client.delete(f"/me/notifications/{items[0]['id']}", headers=auth).status_code == 204
    assert [i["id"] for i in listing(client, auth)["items"]] == [items[1]["id"]]


def test_isolation_and_demo(client, auth, opportunities):
    client.put(f"/me/opportunities/{opportunities['t0']}/saved", headers=auth)
    [item] = listing(client, auth)["items"]
    other = bearer(make_token(str(uuid.uuid4())))
    assert listing(client, other)["items"] == []
    assert client.delete(f"/me/notifications/{item['id']}", headers=other).status_code == 404

    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert listing(client, demo)["items"] == []
    assert client.post("/me/notifications/read", json={}, headers=demo).status_code == 403


def test_old_notifications_are_archived(client, auth, repo, user_id):
    client.get("/me", headers=auth)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    repo.add_notification({"user_id": user_id, "kind": "system", "title": "old", "created_at": old})
    assert listing(client, auth)["items"] == []


def test_actions_bypass_the_sync_throttle(client, auth, opportunities, monkeypatch):
    # Real throttle: the bell's reads are rate-limited, but saving an opportunity
    # or starting the agent must show its notification on the very next read.
    monkeypatch.setattr(notifications, "SYNC_EVERY_S", 300)
    assert listing(client, auth)["items"] == []  # starts the 5-minute window
    client.put(f"/me/opportunities/{opportunities['t0']}/saved", headers=auth)
    client.post("/me/agent/start", headers=auth)
    assert sorted(i["kind"] for i in listing(client, auth)["items"]) == ["deadline", "system"]


def test_first_sync_is_not_throttled_right_after_boot(client, auth, opportunities, monkeypatch):
    # CI machines (and new containers) can be up for less than the throttle window.
    monkeypatch.setattr(notifications.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(notifications, "SYNC_EVERY_S", 300)
    client.put(f"/me/opportunities/{opportunities['t0']}/saved", headers=auth)
    assert [i["kind"] for i in listing(client, auth)["items"]] == ["deadline"]
