from oppradar_ai.ingestion.scam_check import check, score_opportunity
from oppradar_ai.schemas import Opportunity, OpportunityType, ScamLabel


def _opp(description: str, title: str = "Software Engineer", url: str = "https://legit-corp.com/jobs/1") -> Opportunity:
    return Opportunity(
        title=title,
        organization="Legit Corp",
        type=OpportunityType.JOB,
        description=description,
        source_url=url,
        source="test",
    )


def test_normal_job_is_safe():
    verdict = check(_opp("Join our engineering team. 3 years experience with Python required."))
    assert verdict.label is ScamLabel.SAFE
    assert verdict.score < 0.3


def test_payment_request_is_scam():
    verdict = check(
        _opp("Send 2,000 DZD registration fee to apply. Pay now to secure your seat.")
    )
    assert verdict.label is ScamLabel.SCAM
    assert any("payment" in r.lower() or "money" in r.lower() for r in verdict.reasons)


def test_passport_harvesting_flagged():
    verdict = check(
        _opp("Urgent! Send your passport by WhatsApp today for immediate processing. Last chance!")
    )
    assert verdict.label in {ScamLabel.SCAM, ScamLabel.SUSPICIOUS}
    assert verdict.score >= 0.3


def test_too_good_to_be_true():
    verdict = check(_opp("Earn 5000$ per week guaranteed, no skills needed, easy money!"))
    assert verdict.label is ScamLabel.SCAM
    assert verdict.score >= 0.5


def test_scoring_is_deterministic():
    text = "Urgent, pay the application fee now, email us at hr@gmail.com"
    assert score_opportunity(_opp(text)) == score_opportunity(_opp(text))


def test_llm_disabled_by_default_in_check():
    # check() with use_llm=True but no key configured must still return a verdict.
    verdict = check(_opp("Something mildly odd but not clearly a scam."))
    assert isinstance(verdict.score, float)
