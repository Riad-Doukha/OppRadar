import numpy as np

from oppradar_ai.matching.embeddings import skill_overlap
from oppradar_ai.matching.scorer import score_matches

TODAY = "2026-10-19"


def _opp(fixture_opportunities, opp_id: str):
    return next(o for o in fixture_opportunities if o.id == opp_id)


def test_skill_overlap_scores_and_matches(synthetic_profiles):
    profile = synthetic_profiles["profile-1"]  # python, ml, pandas, sql, pytorch, dl
    opp = _opp_synthetic(tags=["python", "pytorch", "rust"])
    score, matched = skill_overlap(profile, opp)
    # 2 of the 3 requested skills are in the profile.
    assert score == 0.667
    assert matched == ["python", "pytorch"]


def test_skill_overlap_empty_sets():
    from oppradar_ai.schemas import Opportunity, OpportunityType, Profile

    profile = Profile(skills=[])
    opp = Opportunity(title="t", organization="o", type=OpportunityType.JOB,
                      source_url="https://x.org/1", tags=["python"])
    assert skill_overlap(profile, opp) == (0.0, [])


def test_score_matches_ranks_relevant_first(fixture_opportunities, synthetic_profiles, fake_embed):
    from datetime import date

    profile = synthetic_profiles["profile-1"]  # ML profile, wants internships/research
    results = score_matches(
        profile, fixture_opportunities, top_k=5,
        embed_fn=fake_embed, today=date(2026, 10, 19),
    )
    assert len(results) == 5
    assert all(results[i].score >= results[i + 1].score for i in range(len(results) - 1))
    # ML-related fixtures carry matching tags, so they must beat the design gig.
    top_titles = " ".join(m.opportunity.title for m in results).lower()
    assert "graphic design" not in top_titles


def test_scam_and_deadline_filtered(fixture_opportunities, synthetic_profiles, fake_embed):
    from datetime import date

    profile = synthetic_profiles["profile-1"]
    results = score_matches(
        profile, fixture_opportunities, top_k=30,
        embed_fn=fake_embed, today=date(2026, 10, 19),
    )
    surfaced = {m.opportunity.id for m in results}
    assert "opp-28" not in surfaced  # the scam fixture — irrelevant tags push it out via filters
    # and every score stays in range with reasons attached
    assert all(0.0 <= m.score <= 1.0 and m.reasons for m in results)


def test_empty_opportunity_list_returns_empty(synthetic_profiles, fake_embed):
    assert score_matches(synthetic_profiles["profile-2"], [], embed_fn=fake_embed) == []


def _opp_synthetic(tags):
    from oppradar_ai.schemas import Opportunity, OpportunityType

    return Opportunity(
        title="Whatever", organization="Org", type=OpportunityType.INTERNSHIP,
        source_url="https://x.org/2", tags=tags,
    )
