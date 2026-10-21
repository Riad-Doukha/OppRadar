from datetime import datetime, timedelta, timezone

from oppradar_ai.schemas import (
    ChatTurn,
    NotificationStatus,
    Profile,
)
from oppradar_ai.store import JsonStore, make_id


def test_make_id_is_deterministic():
    assert make_id("opp", "Title", "Org") == make_id("opp", "Title", "Org")
    assert make_id("opp", "Title", "Org") != make_id("opp", "Other", "Org")


def test_user_roundtrip(tmp_store):
    profile = Profile(user_id="u1", full_name="Synthetic Person", skills=["python"])
    tmp_store.save_user(profile)
    assert tmp_store.get_user("u1") == profile
    assert [p.user_id for p in tmp_store.list_users()] == ["u1"]
    assert tmp_store.get_user("nobody") is None


def test_opportunities_upsert_and_ids(tmp_store, sample_opportunity):
    saved = tmp_store.save_opportunities([sample_opportunity])
    assert saved[0].id.startswith("opp-")
    # saving again with the same id must not duplicate
    tmp_store.save_opportunities([saved[0]])
    assert len(tmp_store.list_opportunities()) == 1
    assert tmp_store.get_opportunity(saved[0].id) == saved[0]


def test_matches_replaced_per_profile(tmp_store, sample_match):
    tmp_store.save_matches("u-test", [sample_match])
    assert len(tmp_store.get_matches("u-test")) == 1
    tmp_store.save_matches("u-test", [])
    assert tmp_store.get_matches("u-test") == []


def test_notification_history_and_daily_cap(tmp_store, sample_notification):
    sent = sample_notification.model_copy(
        update={"status": NotificationStatus.SENT, "created_at": datetime.now(timezone.utc)}
    )
    old = sample_notification.model_copy(
        update={
            "status": NotificationStatus.SENT,
            "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            "opportunity_id": "opp-old",
        }
    )
    tmp_store.add_notifications([sent, old, sample_notification])
    history = tmp_store.notification_history("u-test")
    assert len(history) == 3
    assert tmp_store.sent_count_today("u-test") == 1  # only today's SENT counts


def test_chat_history_append_and_limit(tmp_store):
    for i in range(5):
        tmp_store.append_chat("u1", ChatTurn(role="user", content=f"msg {i}"))
    history = tmp_store.chat_history("u1", limit=3)
    assert [t.content for t in history] == ["msg 2", "msg 3", "msg 4"]


def test_reset_clears_everything(tmp_store, sample_profile, sample_opportunity):
    tmp_store.save_user(sample_profile)
    tmp_store.save_opportunities([sample_opportunity])
    tmp_store.reset()
    assert tmp_store.list_users() == []
    assert tmp_store.list_opportunities() == []


def test_store_is_reusable_across_instances(tmp_store, sample_opportunity):
    tmp_store.save_opportunities([sample_opportunity])
    second = JsonStore(root=tmp_store.root)
    assert len(second.list_opportunities()) == 1
