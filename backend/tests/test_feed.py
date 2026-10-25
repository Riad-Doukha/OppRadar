# Dashboard feed: For you / Closing soon / Saved tabs, Save + Not interested,
# dashboard counts — over the AI fixtures in the in-memory repository.

import json
import uuid
from datetime import date, timedelta

import pytest
from oppradar_ai.schemas import Opportunity

from app.services.ai import opportunity_row
from conftest import AI_DATA, bearer, make_token


@pytest.fixture
def seeded(repo):
    raw = json.loads((AI_DATA / "fixtures" / "opportunities.json").read_text(encoding="utf-8"))
    rows = [opportunity_row(Opportunity.model_validate(item)) for item in raw]
    # Deadlines from 2 days ago to len-3 days ahead, independent of fixture age.
    for i, row in enumerate(rows):
        row["deadline"] = (date.today() + timedelta(days=i - 2)).isoformat()
    repo.upsert_opportunities(rows)
    return rows


def wants(client, auth, *types):
    response = client.patch(
        "/me/onboarding/skills", json={"opportunity_types": list(types)}, headers=auth
    )
    assert response.status_code == 200, response.text


def feed(client, auth, tab="for_you", **params):
    response = client.get(
        "/me/opportunities", params={"tab": tab, "limit": 100, **params}, headers=auth
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_for_you_follows_the_profile_types(client, auth, seeded):
    wanted = seeded[5]["type"]
    wants(client, auth, wanted)
    page = feed(client, auth)
    assert page["items"] and {i["type"] for i in page["items"]} == {wanted}
    assert all(not i["saved"] and not i["dismissed"] for i in page["items"])
    assert all(i["is_new"] for i in page["items"])  # just seeded


def test_for_you_without_types_shows_everything_open(client, auth, seeded):
    assert feed(client, auth)["total"] == len(seeded) - 2


def test_save_unsave_and_saved_tab(client, auth, seeded):
    item = feed(client, auth)["items"][0]
    saved = client.put(f"/me/opportunities/{item['id']}/saved", headers=auth).json()
    assert saved["saved"] is True
    assert [i["id"] for i in feed(client, auth, "saved")["items"]] == [item["id"]]
    assert client.get(f"/me/opportunities/{item['id']}", headers=auth).json()["saved"] is True

    client.delete(f"/me/opportunities/{item['id']}/saved", headers=auth)
    assert feed(client, auth, "saved")["total"] == 0


def test_not_interested_hides_and_unsaves(client, auth, seeded):
    item = feed(client, auth)["items"][0]
    client.put(f"/me/opportunities/{item['id']}/saved", headers=auth)
    dismissed = client.put(f"/me/opportunities/{item['id']}/dismissed", headers=auth).json()
    assert dismissed["dismissed"] is True and dismissed["saved"] is False
    assert item["id"] not in {i["id"] for i in feed(client, auth)["items"]}
    client.delete(f"/me/opportunities/{item['id']}/dismissed", headers=auth)
    assert item["id"] in {i["id"] for i in feed(client, auth)["items"]}


def test_closing_tab_is_the_next_7_days(client, auth, seeded):
    page = feed(client, auth, "closing")
    limit = (date.today() + timedelta(days=7)).isoformat()
    assert page["total"] == 8  # today .. today+7
    assert all(date.today().isoformat() <= i["deadline"] <= limit for i in page["items"])


def test_dashboard_counts(client, auth, seeded):
    item = feed(client, auth)["items"][0]
    client.put(f"/me/opportunities/{item['id']}/saved", headers=auth)
    stats = client.get("/me/dashboard", headers=auth).json()
    assert stats["for_you"] == len(seeded) - 2
    assert stats["new_today"] == len(seeded) - 2
    assert stats["closing_this_week"] == 8
    assert stats["saved"] == 1
    assert stats["applications"] == 0
    assert stats["matching_available"] is False
    assert stats["agent_started_at"] is None


def test_state_is_per_user_and_demo_is_read_only(client, auth, seeded):
    item = feed(client, auth)["items"][0]
    client.put(f"/me/opportunities/{item['id']}/saved", headers=auth)
    other = bearer(make_token(str(uuid.uuid4())))
    assert feed(client, other, "saved")["total"] == 0
    demo = bearer(make_token(demo=True))
    assert client.put(f"/me/opportunities/{item['id']}/saved", headers=demo).status_code == 403


def test_unknown_opportunity_is_404(client, auth, seeded):
    missing = uuid.uuid4()
    assert client.get(f"/me/opportunities/{missing}", headers=auth).status_code == 404
    assert client.put(f"/me/opportunities/{missing}/saved", headers=auth).status_code == 404
