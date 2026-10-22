# Public opportunity browsing over the AI fixtures (as seeded by scripts/seed.py).

import json
import uuid
from datetime import date, timedelta

import pytest
from oppradar_ai.schemas import Opportunity

from app.services.ai import opportunity_row
from conftest import AI_DATA


@pytest.fixture
def seeded(repo):
    raw = json.loads((AI_DATA / "fixtures" / "opportunities.json").read_text(encoding="utf-8"))
    rows = [opportunity_row(Opportunity.model_validate(item)) for item in raw]
    # Pin deadlines relative to today so the test does not depend on fixture age.
    for i, row in enumerate(rows):
        row["deadline"] = (date.today() + timedelta(days=i - 2)).isoformat()
    repo.upsert_opportunities(rows)
    return rows


def test_lists_only_open_opportunities_by_default(client, seeded):
    page = client.get("/opportunities", params={"limit": 100}).json()
    assert page["total"] == len(seeded) - 2  # two deadlines are in the past
    deadlines = [item["deadline"] for item in page["items"]]
    assert deadlines == sorted(deadlines)
    assert client.get("/opportunities", params={"include_expired": True}).json()["total"] == len(
        seeded
    )


def test_filters_by_type_and_text(client, seeded):
    wanted = seeded[5]["type"]
    page = client.get("/opportunities", params={"type": wanted, "limit": 100}).json()
    assert page["items"] and all(item["type"] == wanted for item in page["items"])

    word = seeded[10]["title"].split()[0]
    found = client.get("/opportunities", params={"q": word}).json()["items"]
    assert any(item["title"] == seeded[10]["title"] for item in found)


def test_paginates(client, seeded):
    first = client.get("/opportunities", params={"limit": 5}).json()
    second = client.get("/opportunities", params={"limit": 5, "offset": 5}).json()
    assert len(first["items"]) == 5
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})


def test_reseeding_upserts_on_external_id(client, repo, seeded):
    repo.upsert_opportunities(seeded)
    assert len(repo.opportunities) == len(seeded)


def test_get_one_and_404(client, seeded):
    item = client.get("/opportunities").json()["items"][0]
    assert client.get(f"/opportunities/{item['id']}").json()["title"] == item["title"]
    assert client.get(f"/opportunities/{uuid.uuid4()}").status_code == 404


def test_rejects_unknown_type(client):
    assert client.get("/opportunities", params={"type": "party"}).status_code == 422
