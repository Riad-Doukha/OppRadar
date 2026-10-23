# Matching tests: hard filters (what stays, what is dropped and why), the
# criteria rule-chain, the reproducible 0-100 score and its rule-first reasons
# (the LLM only rephrases, behind its gate). Everything offline: fake provider,
# fake embedder, pinned dates — no network, no model, no real personal data.

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from oppradar_ai.config import get_settings
from oppradar_ai.llm import get_llm
from oppradar_ai.matching import (
    apply_hard_filters,
    check_criteria,
    combine,
    compute_bonus,
    criteria_ratio,
    evaluate_line,
    phrase_reasons,
    phrasing_allowed,
    score_user,
)
from oppradar_ai.matching.criteria import experience_years
from oppradar_ai.matching.reasons import profile_is_empty
from oppradar_ai.schemas import (
    CriteriaStatus,
    DropReason,
    EligibilityCriterion,
    Opportunity,
    OpportunityType,
    PhrasedReasons,
    Profile,
    ScamFlag,
    ScamFlagDetail,
    TrustLevel,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
# The fixtures' own generation date: their deadlines are relative to it, so the
# expiry tests stay deterministic on any machine and any day.
TODAY = date(2026, 10, 21)


def _settings(**updates):
    return get_settings().model_copy(update=updates)


def _opps() -> list[Opportunity]:
    raw = json.loads((FIXTURES / "opportunities.json").read_text(encoding="utf-8"))
    return [Opportunity.model_validate(item) for item in raw]


def _profiles() -> list[Profile]:
    raw = json.loads((FIXTURES / "profiles.json").read_text(encoding="utf-8"))
    return [Profile.model_validate(item) for item in raw]


def _amine() -> Profile:
    return next(profile for profile in _profiles() if profile.user_id == "u-amine")


def _opp(**updates) -> Opportunity:
    """An internship that satisfies u-amine's preferences, unless told otherwise."""
    base: dict = {
        "title": "Test Call",
        "organizer": "Test Org",
        "type": OpportunityType.INTERNSHIP,
        "mode": "remote",
        "funding": "paid",
    }
    base.update(updates)
    return Opportunity(**base)


def _criterion(status: CriteriaStatus) -> EligibilityCriterion:
    return EligibilityCriterion(text="line", status=status)


# --------------------------------------------------------------------------- #
# Hard filters
# --------------------------------------------------------------------------- #
def test_expired_is_dropped_and_a_future_deadline_is_kept() -> None:
    expired = next(o for o in _opps() if o.id == "opp-10")  # deadline 2026-09-21
    kept = next(o for o in _opps() if o.id == "opp-01")  # deadline 2026-12-05
    outcome = apply_hard_filters(_amine(), [expired, kept], today=TODAY)
    assert [d.opportunity_id for d in outcome.dropped] == ["opp-10"]
    assert outcome.dropped[0].reason is DropReason.EXPIRED
    assert [o.id for o in outcome.passed] == ["opp-01"]


def test_a_pinned_earlier_day_keeps_the_same_record() -> None:
    # The expiry check must never depend on the wall clock.
    opp = next(o for o in _opps() if o.id == "opp-10")  # hackathon, deadline 2026-09-21
    karim = next(p for p in _profiles() if p.user_id == "u-karim")  # likes hackathons
    before = apply_hard_filters(karim, [opp], today=date(2026, 9, 15))
    assert [o.id for o in before.passed] == ["opp-10"]
    after = apply_hard_filters(karim, [opp], today=TODAY)
    assert after.dropped[0].reason is DropReason.EXPIRED


def test_null_deadline_is_kept_not_dropped() -> None:
    opp = _opp(deadline=None)
    outcome = apply_hard_filters(_amine(), [opp], today=TODAY)
    assert [o.id for o in outcome.passed] == [opp.id]
    assert outcome.dropped == []


def test_scam_trust_level_and_any_scam_flag_are_dropped() -> None:
    labelled = _opp(trust_level=TrustLevel.SCAM)
    flag = ScamFlagDetail(flag=ScamFlag.APPLICATION_FEE)
    flagged = _opp(trust_level=TrustLevel.UNKNOWN, scam_flags=[flag])
    outcome = apply_hard_filters(_amine(), [labelled, flagged], today=TODAY)
    assert [d.reason for d in outcome.dropped] == [DropReason.SCAM, DropReason.SCAM]
    assert "application_fee" in outcome.dropped[1].detail


def test_preference_mismatches_are_dropped_with_a_reason() -> None:
    job = _opp(type=OpportunityType.JOB)
    onsite = _opp(mode="onsite")
    unfunded = _opp(funding=None)
    outcome = apply_hard_filters(_amine(), [job, onsite, unfunded], today=TODAY)
    assert [d.reason for d in outcome.dropped] == [
        DropReason.TYPE_MISMATCH,
        DropReason.MODE_MISMATCH,
        DropReason.NO_FUNDING,
    ]
    assert all(d.detail for d in outcome.dropped)


def test_missing_country_or_mode_never_filters() -> None:
    # "Unknown"/"" country and a null mode are absence of data, not a mismatch.
    sara = next(p for p in _profiles() if p.user_id == "u-sara")  # countries: Algeria
    unknown = _opp(type=OpportunityType.JOB, country="Unknown")
    unstated = _opp(type=OpportunityType.JOB, mode=None, country="")
    outcome = apply_hard_filters(sara, [unknown, unstated], today=TODAY)
    assert len(outcome.passed) == 2 and outcome.dropped == []


def test_a_scam_labelled_by_the_detector_never_reaches_scoring() -> None:
    # Notebook 05 simulates the detector writing trust_level/scam_flags into
    # the two scam-labelled fixtures before scoring: both must vanish.
    flag = ScamFlagDetail(flag=ScamFlag.BANK_OR_ID_REQUEST)
    labelled = [
        o.model_copy(update={"trust_level": TrustLevel.SCAM, "scam_flags": [flag]})
        for o in _opps()
        if o.id in ("opp-31", "opp-32")
    ]
    outcome = apply_hard_filters(_amine(), labelled, today=TODAY)
    assert outcome.passed == []
    assert {d.reason for d in outcome.dropped} == {DropReason.SCAM}


# --------------------------------------------------------------------------- #
# Criteria rule-chain
# --------------------------------------------------------------------------- #
def test_language_rule_met_missed_and_unknown() -> None:
    profile = _amine()  # arabic, french, english
    assert evaluate_line(profile, "English B2 required").status is CriteriaStatus.MET
    assert evaluate_line(profile, "Japanese required").status is CriteriaStatus.MISSED
    silent = Profile(user_id="u-silent", full_name="Silent")
    assert evaluate_line(silent, "English B2 required").status is CriteriaStatus.UNKNOWN


def test_no_requirement_lines_are_met_without_guessing() -> None:
    for line in ("Open to all", "No skills needed"):
        assert evaluate_line(_amine(), line).status is CriteriaStatus.MET


def test_age_is_flagged_unknown_never_guessed() -> None:
    criterion = evaluate_line(_amine(), "Ages 18-34 only")
    assert criterion.status is CriteriaStatus.UNKNOWN
    assert "age" in criterion.evidence


def test_experience_years_are_counted_from_the_profile_dates() -> None:
    amine = _amine()  # one 3-month internship
    assert experience_years(amine) == pytest.approx(0.25)
    criterion = evaluate_line(amine, "Two years of work experience")
    assert criterion.status is CriteriaStatus.MISSED
    assert "year" in criterion.evidence


def test_degree_level_and_field_rules() -> None:
    amine = _amine()  # MSc in data science
    assert evaluate_line(amine, "Master's students in ML or CS").status is CriteriaStatus.MET
    assert evaluate_line(amine, "PhD only").status is CriteriaStatus.MISSED
    lina = next(p for p in _profiles() if p.user_id == "u-lina")  # humanities BA
    assert evaluate_line(lina, "MSc in CS or NLP").status is CriteriaStatus.MISSED


def test_missing_skills_are_missed_but_unreadable_lines_stay_unknown() -> None:
    missed = evaluate_line(_amine(), "React knowledge")
    assert missed.status is CriteriaStatus.MISSED
    assert "react" in missed.evidence
    assert evaluate_line(_amine(), "Portfolio required").status is CriteriaStatus.UNKNOWN


def test_check_criteria_covers_every_eligibility_line_with_evidence() -> None:
    opp = _opp(eligibility=["Students only", "English required", "React knowledge"])
    criteria = check_criteria(_amine(), opp)
    assert [c.text for c in criteria] == ["Students only", "English required", "React knowledge"]
    assert all(c.evidence for c in criteria)


# --------------------------------------------------------------------------- #
# The score and its parts
# --------------------------------------------------------------------------- #
def test_scoring_weights_sum_to_one() -> None:
    settings = get_settings()
    total = settings.semantic_weight + settings.criteria_weight + settings.bonus_weight
    assert total == pytest.approx(1.0)


def test_combine_uses_the_configured_weights() -> None:
    settings = _settings(semantic_weight=0.5, criteria_weight=0.35, bonus_weight=0.15)
    assert combine(1.0, 1.0, 1.0, settings) == 100.0
    assert combine(0.0, 0.5, 0.5, settings) == 25.0
    assert combine(0.4, 0.6, 0.8, settings) == 53.0


def test_criteria_ratio_is_neutral_when_nothing_is_checkable() -> None:
    assert criteria_ratio([]) == 0.5
    assert criteria_ratio([_criterion(CriteriaStatus.UNKNOWN)]) == 0.5
    checked = [
        _criterion(CriteriaStatus.MET),
        _criterion(CriteriaStatus.MET),
        _criterion(CriteriaStatus.MISSED),
    ]
    assert criteria_ratio(checked) == pytest.approx(0.6667, abs=0.001)


def test_bonus_is_the_mean_of_its_three_signals() -> None:
    verified = _opp(language="fr", trust_level=TrustLevel.VERIFIED)
    bonus, signals = compute_bonus(_amine(), verified)
    assert dict(signals) == {"funding": 1.0, "language": 1.0, "trust": 1.0}
    assert bonus == 1.0


def test_every_score_is_reproducible_from_its_stored_parts() -> None:
    settings = get_settings()
    for profile in _profiles():
        for match in score_user(profile, _opps(), today=TODAY):
            ratio = criteria_ratio(match.criteria)
            assert match.score == combine(match.semantic_similarity, ratio, match.bonus, settings)
            assert 0.0 <= match.score <= 100.0


def test_matches_are_sorted_best_first_and_schema_valid() -> None:
    for profile in _profiles():
        matches = score_user(profile, _opps(), today=TODAY)
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)
        for match in matches:
            assert type(match).model_validate(match.model_dump()).score == match.score


def test_unmet_requirements_list_exactly_the_missed_rows() -> None:
    for match in score_user(_amine(), _opps(), today=TODAY):
        missed = [c.text for c in match.criteria if c.status is CriteriaStatus.MISSED]
        assert match.unmet_requirements == missed


def test_scoring_is_deterministic_offline() -> None:
    first = score_user(_amine(), _opps(), today=TODAY)
    second = score_user(_amine(), _opps(), today=TODAY)
    assert [m.model_dump() for m in first] == [m.model_dump() for m in second]


# --------------------------------------------------------------------------- #
# Edge cases from the checklist
# --------------------------------------------------------------------------- #
def test_language_mismatch_lowers_the_bonus_but_keeps_the_row() -> None:
    japanese = _opp(language="ja")
    matches = score_user(_amine(), [japanese], today=TODAY)
    assert len(matches) == 1  # a mismatch is a signal, never a hard filter
    bonus, signals = compute_bonus(_amine(), japanese)
    assert dict(signals)["language"] == 0.0
    assert matches[0].bonus == bonus


def test_missing_location_and_country_still_score() -> None:
    nowhere = _opp(location="", country="")
    assert len(score_user(_amine(), [nowhere], today=TODAY)) == 1


def test_empty_profile_is_flagged_first_and_still_scores() -> None:
    empty = Profile(user_id="u-empty", full_name="")
    assert profile_is_empty(empty)
    matches = score_user(empty, _opps(), today=TODAY)
    assert len(matches) == len(_opps()) - 1  # only the expired one goes
    assert matches[0].top_reasons[0].startswith("Your profile is empty")


# --------------------------------------------------------------------------- #
# Reasons: rules write them, the model only rephrases (behind its gate)
# --------------------------------------------------------------------------- #
def test_the_gate_is_closed_for_the_fake_provider_and_without_the_opt_in() -> None:
    assert not phrasing_allowed(_settings(run_live_llm=True))  # provider stays fake
    assert not phrasing_allowed(_settings(run_live_llm=False, llm_provider="gemini"))


def test_every_match_keeps_rule_reasons_when_the_gate_is_closed() -> None:
    for profile in _profiles():
        for match in score_user(profile, _opps(), today=TODAY):
            assert match.reasons_source == "rules"
            assert 1 <= len(match.top_reasons) <= 3
            assert all(reason.strip() for reason in match.top_reasons)


def test_phrase_reasons_rewords_but_keeps_the_count() -> None:
    opp = _opp(title="ML Grant")
    match = score_user(_amine(), [opp], today=TODAY)[0]
    phrased = phrase_reasons(match.top_reasons, opp, get_llm())
    assert len(phrased) == len(match.top_reasons)
    assert phrased[0].startswith("[fake]")  # the canned model marks its lines


def test_the_model_sees_reasons_and_public_facts_never_the_profile() -> None:
    class SpyLLM:
        """Records the prompt instead of answering, to inspect what was sent."""

        def __init__(self) -> None:
            self.prompts: list[str] = []

        def structured(self, prompt: str, schema, system: str | None = None) -> PhrasedReasons:
            self.prompts.append(prompt)
            return PhrasedReasons(reasons=["reworded"])

    amine = _amine()
    opp = _opp(title="ML Grant")
    match = score_user(_amine(), [opp], today=TODAY)[0]
    spy = SpyLLM()
    phrase_reasons(match.top_reasons, opp, spy)
    seen = " ".join(spy.prompts)
    assert "ML Grant" in seen and match.top_reasons[0] in seen
    for private in (amine.full_name, "NAMOCO Analytics"):
        assert private not in seen
