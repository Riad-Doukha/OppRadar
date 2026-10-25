# Settings pages: alert rules, new consents, retention, agent settings, delete account.

import uuid

from conftest import bearer, make_token

CV_PDF_MAGIC = b"%PDF-1.4 minimal"


def test_defaults(client, auth):
    me = client.get("/me", headers=auth).json()
    n = me["notifications"]
    assert n["rule_new_match"] and n["rule_deadline_reminders"] and n["rule_weekly_digest"]
    assert n["rule_profile_tips"] is False and n["bundle_non_urgent"] is False
    assert me["history_retention"] == "12_months"
    agent = me["agent_settings"]
    assert agent["auto_scan"] is True and agent["scope"] == "all_dz" and agent["min_score"] == 55
    assert agent["languages"] == ["en", "fr", "ar"]
    assert all(agent["source_groups"].values())


def test_alert_rules_and_new_consents_save(client, auth):
    body = {
        "rule_profile_tips": True,
        "bundle_non_urgent": True,
        "rule_weekly_digest": False,
        "consents": {"ai_drafts": True, "chat_history": True, "anonymized_stats": False},
    }
    me = client.patch("/me/onboarding/alerts", json=body, headers=auth).json()
    assert me["notifications"]["rule_profile_tips"] is True
    assert me["notifications"]["bundle_non_urgent"] is True
    assert me["notifications"]["rule_weekly_digest"] is False
    assert {"ai_drafts", "chat_history"} <= set(me["consents"])
    assert "anonymized_stats" not in me["consents"]


def test_settings_patch_merges_agent_settings(client, auth):
    me = client.patch(
        "/me/settings",
        json={
            "history_retention": "never",
            "agent": {"scope": "remote", "source_groups": {"events": False}},
        },
        headers=auth,
    ).json()
    assert me["history_retention"] == "never"
    assert me["agent_settings"]["scope"] == "remote"
    assert me["agent_settings"]["source_groups"] == {
        "universities": True, "companies": True, "events": False, "international": True,
    }  # fmt: skip
    # A later patch keeps earlier choices.
    me = client.patch("/me/settings", json={"agent": {"min_score": 70}}, headers=auth).json()
    assert me["agent_settings"]["scope"] == "remote" and me["agent_settings"]["min_score"] == 70


def test_settings_validation(client, auth):
    assert (
        client.patch(
            "/me/settings", json={"history_retention": "forever"}, headers=auth
        ).status_code
        == 422
    )
    assert (
        client.patch("/me/settings", json={"agent": {"languages": []}}, headers=auth).status_code
        == 422
    )
    assert (
        client.patch(
            "/me/settings", json={"agent": {"source_groups": {"tiktok": True}}}, headers=auth
        ).status_code
        == 422
    )


def test_delete_account_removes_data_and_files(client, auth, repo, user_id):
    client.patch("/me/onboarding/about", json={"wilaya": "Oran"}, headers=auth)
    client.post("/me/experiences", json={"title": "Intern"}, headers=auth)
    upload = client.post(
        "/documents",
        files={"file": ("cv.pdf", CV_PDF_MAGIC, "application/pdf")},
        data={"consent_ai_processing": "true"},
        headers=auth,
    )
    assert upload.status_code == 202
    assert repo.files

    assert client.delete("/me", headers=auth).status_code == 204
    assert user_id not in repo.profiles
    assert not repo.files
    assert all(r["user_id"] != user_id for rows in repo.children.values() for r in rows)
    assert all(c["user_id"] != user_id for c in repo.consents)


def test_demo_cannot_change_settings_or_delete(client):
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert (
        client.patch("/me/settings", json={"history_retention": "never"}, headers=demo).status_code
        == 403
    )
    assert client.delete("/me", headers=demo).status_code == 403
