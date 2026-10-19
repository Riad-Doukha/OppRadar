from datetime import date

from oppradar_ai.matching.filters import hard_filters
from oppradar_ai.schemas import Mode, OpportunityType, Preferences

TODAY = date(2026, 10, 19)


def _opp(fixture_opportunities, opp_id: str):
    return next(o for o in fixture_opportunities if o.id == opp_id)


def test_past_deadline_rejected(fixture_opportunities, synthetic_profiles):
    profile = synthetic_profiles["profile-1"]
    opp = _opp(fixture_opportunities, "opp-01").model_copy(update={"deadline": date(2026, 1, 1)})
    result = hard_filters(profile, opp, today=TODAY)
    assert not result.passed
    assert any("deadline passed" in r for r in result.reasons)


def test_future_deadline_passes(fixture_opportunities, synthetic_profiles):
    profile = synthetic_profiles["profile-1"]
    assert hard_filters(profile, _opp(fixture_opportunities, "opp-01"), today=TODAY).passed


def test_mode_preference_enforced(fixture_opportunities):
    profile = synthetic_profiles_stub(modes=[Mode.REMOTE])
    onsite = _opp(fixture_opportunities, "opp-04")  # DP World, onsite
    result = hard_filters(profile, onsite, today=TODAY)
    assert not result.passed
    assert any("mode" in r for r in result.reasons)


def test_country_preference_enforced(fixture_opportunities):
    profile = synthetic_profiles_stub(countries=["Algeria"])
    france = _opp(fixture_opportunities, "opp-14")  # Research assistant, France
    assert not hard_filters(profile, france, today=TODAY).passed


def test_type_preference_enforced(fixture_opportunities):
    profile = synthetic_profiles_stub(types=[OpportunityType.SCHOLARSHIP])
    job = _opp(fixture_opportunities, "opp-17")  # DevOps job
    assert not hard_filters(profile, job, today=TODAY).passed


def test_empty_preferences_pass_everything(fixture_opportunities):
    from oppradar_ai.schemas import Profile

    profile = Profile(full_name="Anyone", preferences=Preferences())
    for opp in fixture_opportunities:
        assert hard_filters(profile, opp, today=TODAY).passed, opp.title


def synthetic_profiles_stub(**prefs) -> "Profile":
    from oppradar_ai.schemas import Profile

    return Profile(full_name="Stub", preferences=Preferences(**prefs))
