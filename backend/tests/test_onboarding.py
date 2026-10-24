# The 5-step onboarding wizard from the Figma design: autosave, validation,
# completion rules, experience/certificate CRUD.

import uuid

from conftest import bearer, make_token

ABOUT = {
    "full_name": "Amine Benali",
    "birth_year": 2003,
    "nationality": "Algerian",
    "country": "Algeria",
    "wilaya": "Algiers",
    "languages": [
        {"language": "Arabic", "level": "fluent"},
        {"language": "French", "level": "good"},
        {"language": "English", "level": "fluent"},
    ],
}
EDUCATION = {
    "education_level": "licence",
    "field_of_study": "Computer Science",
    "institution": "ENSIA",
    "current_year": 3,
    "graduation_year": 2028,
    "gpa_value": 3.1,
    "gpa_scale": 4,
}
SKILLS = {
    "skills": [
        {"name": "Python", "level": "advanced"},
        {"name": "SQL", "level": "intermediate"},
        {"name": "React", "level": "intermediate"},
        {"name": "Data analysis"},
    ],
    "interests": ["AI", "Data", "Volunteering"],
    "opportunity_types": ["hackathon", "datathon", "scholarship", "internship"],
    "preferred_location": "algeria",
    "availability": "part_time_10_20",
}
GOALS = {
    "goal": "I want to join international hackathons and find an internship.",
    "links": [
        {"kind": "linkedin", "url": "linkedin.com/in/amine-benali"},
        {"kind": "github", "url": "https://github.com/aminebz"},
    ],
}
ALERTS = {
    "email_enabled": True,
    "telegram_enabled": True,
    "threshold": 75,
    "frequency": "daily",
    "quiet_start": "22:00",
    "quiet_end": "07:00",
    "consents": {"terms_privacy": True, "agent_matching": True},
}


def fill_all(client, headers):
    for step, body in (
        ("about", ABOUT),
        ("education", EDUCATION),
        ("skills", SKILLS),
        ("goals", GOALS),
        ("alerts", ALERTS),
    ):
        response = client.patch(f"/me/onboarding/{step}", json=body, headers=headers)
        assert response.status_code == 200, response.text
    return response.json()


def test_full_wizard_then_complete(client, auth):
    me = fill_all(client, auth)
    assert me["onboarding"]["step"] == 5
    assert me["onboarding"]["missing"] == []
    assert [lang["language"] for lang in me["languages"]] == ["Arabic", "French", "English"]
    assert [s["name"] for s in me["skills"]][:2] == ["Python", "SQL"]
    assert me["links"][0]["url"] == "https://linkedin.com/in/amine-benali"
    assert me["notifications"]["frequency"] == "daily"
    assert sorted(me["consents"]) == ["agent_matching", "terms_privacy"]
    assert 0.8 < me["completeness"] <= 1

    done = client.post("/me/onboarding/complete", headers=auth)
    assert done.status_code == 200
    assert done.json()["onboarding"]["completed_at"] is not None


def test_complete_lists_missing_required_fields(client, auth):
    client.patch("/me/onboarding/about", json={"birth_year": 2003}, headers=auth)
    response = client.post("/me/onboarding/complete", headers=auth)
    assert response.status_code == 422
    missing = response.json()["detail"]["missing"]
    assert "about.wilaya" in missing
    assert "skills.skills" in missing
    assert "alerts.consent.terms_privacy" in missing
    assert "about.birth_year" not in missing


def test_autosave_only_changes_sent_fields(client, auth):
    client.patch("/me/onboarding/about", json=ABOUT, headers=auth)
    me = client.patch("/me/onboarding/about", json={"wilaya": "Oran"}, headers=auth).json()
    assert me["wilaya"] == "Oran"
    assert me["birth_year"] == 2003
    assert len(me["languages"]) == 3  # not sent -> untouched


def test_sent_list_replaces_stored_list(client, auth):
    client.patch("/me/onboarding/about", json=ABOUT, headers=auth)
    me = client.patch(
        "/me/onboarding/about",
        json={"languages": [{"language": "Tamazight", "level": "basic"}]},
        headers=auth,
    ).json()
    assert [(lang["language"], lang["level"]) for lang in me["languages"]] == [
        ("Tamazight", "basic")
    ]


def test_skills_are_deduplicated_case_insensitively(client, auth):
    body = {
        "skills": [{"name": "Python"}, {"name": "python", "level": "advanced"}, {"name": "SQL"}]
    }
    me = client.patch("/me/onboarding/skills", json=body, headers=auth).json()
    assert [s["name"] for s in me["skills"]] == ["Python", "SQL"]
    assert "skills.skills" in me["onboarding"]["missing"]  # fewer than 3


def test_step_never_goes_backwards(client, auth):
    client.patch("/me/onboarding/skills", json={"interests": ["AI"]}, headers=auth)
    me = client.patch("/me/onboarding/about", json={"wilaya": "Algiers"}, headers=auth).json()
    assert me["onboarding"]["step"] == 3


def test_rejects_unknown_fields_and_values(client, auth):
    assert client.patch("/me/onboarding/about", json={"age": 22}, headers=auth).status_code == 422
    assert (
        client.patch(
            "/me/onboarding/skills", json={"preferred_location": "mars"}, headers=auth
        ).status_code
        == 422
    )
    assert (
        client.patch("/me/onboarding/goals", json={"goal": "too short"}, headers=auth).status_code
        == 422
    )
    assert (
        client.patch("/me/onboarding/alerts", json={"threshold": 40}, headers=auth).status_code
        == 422
    )


def test_gpa_needs_value_and_scale_within_range(client, auth):
    only_value = client.patch("/me/onboarding/education", json={"gpa_value": 3.1}, headers=auth)
    assert only_value.status_code == 422
    over = client.patch(
        "/me/onboarding/education", json={"gpa_value": 15, "gpa_scale": 4}, headers=auth
    )
    assert over.status_code == 422
    ok = client.patch(
        "/me/onboarding/education", json={"gpa_value": 15.5, "gpa_scale": 20}, headers=auth
    )
    assert ok.status_code == 200
    assert ok.json()["gpa_scale"] == 20


def test_quiet_hours_need_both_ends_and_can_be_cleared(client, auth):
    half = client.patch("/me/onboarding/alerts", json={"quiet_start": "23:00"}, headers=auth)
    assert half.status_code == 422
    me = client.patch(
        "/me/onboarding/alerts", json={"clear_quiet_hours": True}, headers=auth
    ).json()
    assert me["notifications"]["quiet_start"] is None


def test_consents_can_be_revoked(client, auth):
    client.patch("/me/onboarding/alerts", json=ALERTS, headers=auth)
    me = client.patch(
        "/me/onboarding/alerts", json={"consents": {"agent_matching": False}}, headers=auth
    ).json()
    assert me["consents"] == ["terms_privacy"]


def test_at_least_one_alert_channel_required(client, auth):
    fill_all(client, auth)
    me = client.patch(
        "/me/onboarding/alerts",
        json={"email_enabled": False, "telegram_enabled": False},
        headers=auth,
    ).json()
    assert "alerts.channel" in me["onboarding"]["missing"]


def test_experience_crud_is_scoped_to_owner(client, auth):
    created = client.post(
        "/me/experiences",
        json={
            "kind": "internship",
            "title": "Data Analyst Intern",
            "organization": "Yassir",
            "year": 2024,
        },
        headers=auth,
    )
    assert created.status_code == 201
    exp_id = created.json()["id"]

    edited = client.patch(f"/me/experiences/{exp_id}", json={"year": 2025}, headers=auth)
    assert edited.json()["year"] == 2025
    assert edited.json()["title"] == "Data Analyst Intern"

    stranger = bearer(make_token(str(uuid.uuid4())))
    assert (
        client.patch(f"/me/experiences/{exp_id}", json={"year": 1999}, headers=stranger).status_code
        == 404
    )
    assert client.delete(f"/me/experiences/{exp_id}", headers=stranger).status_code == 404

    assert client.delete(f"/me/experiences/{exp_id}", headers=auth).status_code == 204
    assert client.get("/me", headers=auth).json()["experiences"] == []


def test_certificate_crud(client, auth):
    created = client.post(
        "/me/certificates",
        json={"title": "Python for Data Science", "issuer": "IBM", "year": 2023},
        headers=auth,
    ).json()
    me = client.get("/me", headers=auth).json()
    assert me["certificates"][0]["id"] == created["id"]
    assert client.delete(f"/me/certificates/{created['id']}", headers=auth).status_code == 204


def test_users_do_not_see_each_other(client, auth):
    fill_all(client, auth)
    other = client.get(
        "/me", headers=bearer(make_token(str(uuid.uuid4()), full_name="Sara"))
    ).json()
    assert other["full_name"] == "Sara"
    assert other["skills"] == []


def test_agent_start_turns_matching_on(client, auth):
    first = client.post("/me/agent/start", headers=auth)
    assert first.status_code == 202
    assert first.json()["status"] == "running"
    again = client.post("/me/agent/start", headers=auth).json()
    assert again["agent_started_at"] == first.json()["agent_started_at"]  # idempotent
