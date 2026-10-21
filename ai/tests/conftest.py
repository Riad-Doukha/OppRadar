# Test bootstrap: force the offline fake provider and a throwaway data dir
# BEFORE any test imports oppradar_ai, so no .env key or real cache is touched.

import os
import tempfile

os.environ["LLM_PROVIDER"] = "fake"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="oppradar-test-")

import pytest  # noqa: E402

from oppradar_ai.schemas import (  # noqa: E402
    MatchResult,
    Notification,
    Opportunity,
    OpportunityType,
    Profile,
    TrustLevel,
)


@pytest.fixture
def sample_opportunity() -> Opportunity:
    """One well-formed opportunity used across tests."""
    return Opportunity(
        title="Machine Learning Intern",
        organizer="Ooredoo Algerie",
        type=OpportunityType.INTERNSHIP,
        mode="hybrid",
        location="Algiers",
        country="Algeria",
        deadline=None,
        funding="15,000 DZD/month",
        eligibility=["Students only", "Python required"],
        benefits=["Mentorship"],
        summary="Predictive models for telecom churn.",
        url="https://example.org/jobs/ml-intern",
        source="test",
        trust_level=TrustLevel.LIKELY_SAFE,
    )


@pytest.fixture
def sample_profile() -> Profile:
    """A minimal synthetic profile (no real personal data)."""
    return Profile(
        user_id="u-test",
        full_name="Test User",
        headline="Data science student",
        skills=["python", "machine learning", "sql"],
        languages=["arabic", "french", "english"],
        country="Algeria",
        summary="Data science student in Algiers looking for ML internships.",
    )


@pytest.fixture
def sample_match(sample_opportunity, sample_profile) -> MatchResult:
    return MatchResult(
        profile_id=sample_profile.user_id,
        opportunity=sample_opportunity,
        score=75.0,
        semantic_similarity=0.7,
        top_reasons=["Matches your skills", "Close to your interests", "Remote friendly"],
    )


@pytest.fixture
def sample_notification(sample_opportunity, sample_profile) -> Notification:
    return Notification(
        profile_id=sample_profile.user_id,
        opportunity_id=sample_opportunity.id or "opp-test",
        title=sample_opportunity.title,
        reason="Matches your skills: python",
        score=75.0,
        deadline=sample_opportunity.deadline,
        url=sample_opportunity.url,
    )


@pytest.fixture
def tmp_store(tmp_path):
    """An isolated JsonStore in a pytest temp dir."""
    from oppradar_ai.store import JsonStore

    return JsonStore(root=tmp_path / "store")
