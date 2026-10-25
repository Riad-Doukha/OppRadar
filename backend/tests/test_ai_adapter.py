# services/ai.py: CV extraction -> onboarding prefill, web profile -> AI Profile.

import json
from datetime import date

from oppradar_ai.schemas import OpportunityType

from app.models import Me, OnboardingStatus
from app.services.ai import cv_prefill, headline, to_ai_profile
from conftest import AI_DATA

TODAY = date(2026, 10, 22)


def ground_truth(name: str) -> dict:
    return json.loads((AI_DATA / "samples" / "ground_truth" / name).read_text(encoding="utf-8"))


def test_prefill_from_cv_ground_truth():
    cv = ground_truth("cv_amine.json")
    cv["languages"] = ["Arabic (native)", "French - B2", "English: basic"]
    cv["links"] = ["https://github.com/example-user/churn-toolkit", "linkedin.com/in/amine"]
    prefill = cv_prefill(cv, today=TODAY)

    assert prefill.about.full_name == "Amine Kaddour"
    assert prefill.about.country == "Algeria"
    assert [(lang.language, lang.level) for lang in prefill.about.languages] == [
        ("Arabic", "fluent"),
        ("French", "good"),
        ("English", "basic"),
    ]
    assert prefill.education.education_level == "master"  # "MSc"
    assert prefill.education.field_of_study == "Data Science"
    assert prefill.education.graduation_year == 2027
    assert prefill.education.current_year == 2  # started 2025
    assert [s.name for s in prefill.skills.skills][:3] == ["python", "sql", "pandas"]
    assert [link.kind for link in prefill.goals.links] == ["github", "linkedin"]
    assert prefill.experiences[0].kind == "internship"
    assert prefill.experiences[0].year == 2025
    assert prefill.certificates[0].issuer == "ALX Africa"


def test_prefill_tolerates_an_empty_extraction():
    prefill = cv_prefill({}, today=TODAY)
    assert prefill.about.full_name is None
    assert prefill.education.education_level is None
    assert prefill.experiences == []


def make_me(**fields) -> Me:
    return Me(
        user_id="00000000-0000-0000-0000-000000000001",
        onboarding=OnboardingStatus(step=5),
        **fields,
    )


def test_headline_matches_review_screen():
    me = make_me(
        current_year=3, field_of_study="Computer Science", institution="ENSIA", wilaya="Algiers"
    )
    assert headline(me) == "3rd-year Computer Science · ENSIA, Algiers"


def test_to_ai_profile_maps_types_the_ai_enum_lacks():
    me = make_me(
        full_name="Amine Benali",
        opportunity_types=["datathon", "hackathon", "competition", "internship"],
        preferred_location="algeria",
        skills=[{"name": "Python", "level": "advanced"}],
        languages=[{"language": "Arabic", "level": "fluent"}],
        goal="I want to join international hackathons.",
    )
    profile = to_ai_profile(me)
    assert profile.preferences.types == [
        OpportunityType.HACKATHON,
        OpportunityType.OTHER,
        OpportunityType.INTERNSHIP,
    ]
    assert profile.preferences.countries == ["Algeria"]
    assert profile.skills == ["Python"]
    assert profile.languages == ["Arabic (fluent)"]
    assert "hackathons" in profile.summary
