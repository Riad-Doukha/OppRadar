from datetime import date

import pytest
from pydantic import ValidationError

from oppradar_ai.schemas import (
    CriteriaStatus,
    EligibilityCriterion,
    FieldConfidence,
    MatchResult,
    NotificationStatus,
    Opportunity,
    OpportunityType,
    Profile,
    ScamFlag,
    TrustLevel,
)


class TestOpportunity:
    def test_blank_title_rejected(self):
        with pytest.raises(ValidationError):
            Opportunity(title="  ", organizer="Org")

    def test_roundtrip_json(self, sample_opportunity):
        again = Opportunity.model_validate(sample_opportunity.model_dump(mode="json"))
        assert again == sample_opportunity

    def test_is_expired(self, sample_opportunity):
        past = sample_opportunity.model_copy(update={"deadline": date(2020, 1, 1)})
        assert past.is_expired
        assert not sample_opportunity.is_expired  # deadline None -> not expired

    def test_to_verify_lists_low_confidence(self, sample_opportunity):
        opp = sample_opportunity.model_copy(
            update={
                "field_confidences": [
                    FieldConfidence(field="title", confidence=0.95),
                    FieldConfidence(field="deadline", confidence=0.3, needs_review=True),
                ]
            }
        )
        assert [fc.field for fc in opp.to_verify()] == ["deadline"]

    def test_enums_have_expected_values(self):
        assert OpportunityType.SCHOLARSHIP.value == "scholarship"
        assert TrustLevel.SCAM.value == "scam"
        assert ScamFlag.APPLICATION_FEE.value == "application_fee"


class TestProfile:
    def test_to_verify(self, sample_profile):
        profile = sample_profile.model_copy(
            update={
                "field_confidences": [
                    FieldConfidence(field="skills", confidence=0.9),
                    FieldConfidence(field="education", confidence=0.2, needs_review=True),
                ]
            }
        )
        assert [fc.field for fc in profile.to_verify()] == ["education"]

    def test_completeness_bounds(self):
        with pytest.raises(ValidationError):
            Profile(completeness=1.5)


class TestMatchResult:
    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            MatchResult(profile_id="u", opportunity=_opp(), score=101)
        with pytest.raises(ValidationError):
            MatchResult(profile_id="u", opportunity=_opp(), score=-1)

    def test_default_criteria_status_unknown(self):
        criterion = EligibilityCriterion(text="Bachelor's degree")
        assert criterion.status is CriteriaStatus.UNKNOWN


class TestNotification:
    def test_defaults(self, sample_notification):
        assert sample_notification.status is NotificationStatus.PENDING
        assert sample_notification.created_at is not None


def _opp() -> Opportunity:
    return Opportunity(title="t", organizer="o")
