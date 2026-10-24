# Notification tests: threshold, quiet hours (22-08), the daily cap, digest
# mode and the "never twice for the same user + opportunity" rule. Pure
# function with a pinned clock — nothing is sent, stored or slept on.

from datetime import date, datetime

from oppradar_ai.config import get_settings
from oppradar_ai.matching import decide_notifications, in_quiet_hours, prefs_from_settings
from oppradar_ai.schemas import (
    MatchResult,
    Notification,
    NotificationMode,
    NotificationPrefs,
    NotificationStatus,
    Opportunity,
    OpportunityType,
)

# Local wall clock (naive = "the user's own time", like the default now()).
NOON = datetime(2026, 10, 21, 12, 0)


def _settings(**updates):
    return get_settings().model_copy(update=updates)


def _match(opp_id: str = "opp-1", score: float = 90.0) -> MatchResult:
    opportunity = Opportunity(
        id=opp_id,
        title=f"Call {opp_id}",
        organizer="Test Org",
        type=OpportunityType.INTERNSHIP,
        deadline=date(2026, 12, 1),
        url=f"https://example.org/{opp_id}",
    )
    return MatchResult(
        profile_id="u-test",
        opportunity=opportunity,
        score=score,
        semantic_similarity=0.5,
        top_reasons=["Requirement met: Python"],
    )


def _note(
    opp_id: str,
    status: NotificationStatus,
    *,
    when: datetime = datetime(2026, 10, 21, 9, 0),
) -> Notification:
    return Notification(
        profile_id="u-test",
        opportunity_id=opp_id,
        title=f"Call {opp_id}",
        score=90.0,
        status=status,
        created_at=when,
    )


def _prefs(**updates) -> NotificationPrefs:
    base: dict = {
        "profile_id": "u-test",
        "mode": NotificationMode.INSTANT,
        "daily_cap": 5,
        "quiet_hours_start": 22,
        "quiet_hours_end": 8,
        "threshold": 70.0,
    }
    base.update(updates)
    return NotificationPrefs(**base)


def test_a_match_below_the_threshold_is_not_a_notification() -> None:
    assert decide_notifications([_match(score=69.9)], _prefs(), [], now=NOON) == []


def test_instant_outside_quiet_hours_is_sent_with_its_reason() -> None:
    (note,) = decide_notifications([_match()], _prefs(), [], now=NOON)
    assert note.status is NotificationStatus.SENT
    assert note.suppressed_reason is None
    assert note.reason == "Requirement met: Python"
    assert note.created_at == NOON
    assert note.deadline == date(2026, 12, 1)


def test_quiet_hours_defer_instead_of_send() -> None:
    late_night = datetime(2026, 10, 21, 23, 30)
    early_morning = datetime(2026, 10, 21, 6, 0)
    (at_night,) = decide_notifications([_match()], _prefs(), [], now=late_night)
    (in_the_morning,) = decide_notifications([_match()], _prefs(), [], now=early_morning)
    for note in (at_night, in_the_morning):
        assert note.status is NotificationStatus.PENDING
        assert "quiet hours" in (note.suppressed_reason or "")


def test_quiet_hours_wrap_midnight_and_equal_bounds_never_apply() -> None:
    assert in_quiet_hours(datetime(2026, 1, 1, 23, 0), 22, 8)
    assert in_quiet_hours(datetime(2026, 1, 1, 2, 0), 22, 8)
    assert not in_quiet_hours(datetime(2026, 1, 1, 8, 0), 22, 8)
    assert not in_quiet_hours(datetime(2026, 1, 1, 12, 0), 22, 22)


def test_the_daily_cap_defers_the_rest_to_tomorrow() -> None:
    history = [_note(f"opp-{i}", NotificationStatus.SENT) for i in range(1, 6)]
    (note,) = decide_notifications([_match("opp-9")], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.PENDING
    assert "daily cap" in (note.suppressed_reason or "")


def test_only_todays_sends_count_toward_the_cap() -> None:
    yesterday = datetime(2026, 10, 20, 9, 0)
    history = [_note(f"opp-{i}", NotificationStatus.SENT, when=yesterday) for i in range(1, 6)]
    (note,) = decide_notifications([_match("opp-9")], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.SENT


def test_the_cap_counts_as_it_goes_within_one_run() -> None:
    matches = [_match(f"opp-{i}") for i in range(1, 5)]
    notes = decide_notifications(matches, _prefs(daily_cap=2), [], now=NOON)
    assert [n.status for n in notes] == [
        NotificationStatus.SENT,
        NotificationStatus.SENT,
        NotificationStatus.PENDING,
        NotificationStatus.PENDING,
    ]


def test_digest_mode_queues_everything_with_its_mode() -> None:
    (note,) = decide_notifications([_match()], _prefs(mode=NotificationMode.DIGEST), [], now=NOON)
    assert note.status is NotificationStatus.PENDING
    assert note.mode is NotificationMode.DIGEST
    assert "digest" in (note.suppressed_reason or "")


def test_never_notify_the_same_opportunity_twice() -> None:
    history = [_note("opp-1", NotificationStatus.SENT)]
    (note,) = decide_notifications([_match("opp-1")], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.SUPPRESSED
    assert "already" in (note.suppressed_reason or "")


def test_a_still_pending_alert_also_blocks_a_second_one() -> None:
    history = [_note("opp-1", NotificationStatus.PENDING)]
    (note,) = decide_notifications([_match("opp-1")], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.SUPPRESSED


def test_suppressed_history_does_not_block_a_fresh_alert() -> None:
    history = [_note("opp-1", NotificationStatus.SUPPRESSED)]
    (note,) = decide_notifications([_match("opp-1")], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.SENT


def test_an_id_less_opportunity_is_deduped_by_its_url() -> None:
    match = _match("opp-x")
    match.opportunity.id = ""
    history = [
        _note(match.opportunity.url, NotificationStatus.SENT),
    ]
    (note,) = decide_notifications([match], _prefs(), history, now=NOON)
    assert note.status is NotificationStatus.SUPPRESSED
    assert note.opportunity_id == match.opportunity.url


def test_decisions_are_pure_and_repeatable_matches_stay_untouched() -> None:
    matches = [_match(f"opp-{i}") for i in range(1, 4)]
    before = [m.model_dump() for m in matches]
    first = decide_notifications(matches, _prefs(), [], now=NOON)
    second = decide_notifications(matches, _prefs(), [], now=NOON)
    assert [m.model_dump() for m in matches] == before
    assert [n.model_dump() for n in first] == [n.model_dump() for n in second]


def test_preferences_come_from_the_configuration_not_hardcoded_values() -> None:
    settings = get_settings()
    prefs = prefs_from_settings("u-amine")
    assert prefs.profile_id == "u-amine"
    assert prefs.daily_cap == settings.daily_instant_cap
    assert prefs.threshold == settings.notify_threshold
    assert prefs.quiet_hours_start == settings.quiet_hours_start
    assert prefs.quiet_hours_end == settings.quiet_hours_end


def test_the_daily_or_weekly_settings_spelling_becomes_digest_mode() -> None:
    weekly = prefs_from_settings("u-test", _settings(digest_mode="weekly"))
    daily = prefs_from_settings("u-test", _settings(digest_mode="daily"))
    assert weekly.mode is NotificationMode.DIGEST
    assert daily.mode is NotificationMode.DIGEST
