from datetime import date

from oppradar_ai.ingestion.dedupe import canonical_url, dedupe, normalize_title, similarity
from oppradar_ai.schemas import Opportunity, OpportunityType


def _opp(url: str, title: str, org: str = "Acme", **kwargs) -> Opportunity:
    return Opportunity(
        title=title,
        organization=org,
        type=OpportunityType.INTERNSHIP,
        source_url=url,
        **kwargs,
    )


class TestCanonicalUrl:
    def test_strips_tracking_params(self):
        assert (
            canonical_url("https://Example.org/jobs/1?utm_source=x&fbclid=y&id=7")
            == "https://example.org/jobs/1?id=7"
        )

    def test_strips_fragment_and_trailing_slash(self):
        assert canonical_url("https://a.b/c/#section") == "https://a.b/c"

    def test_preserves_meaningful_query(self):
        assert "page=2" in canonical_url("https://a.b/?page=2")


class TestNormalizeTitle:
    def test_case_and_punctuation_insensitive(self):
        assert normalize_title("Senior  C++ Developer!") == normalize_title("senior c developer")


def test_dedupe_merges_same_url():
    a = _opp("https://x.org/j?a=1", "ML Intern", "Ooredoo", description="short")
    b = _opp("https://x.org/j?utm_campaign=tw", "ML Intern", "Ooredoo",
             description="a much longer and richer description here")
    result = dedupe([a, b])
    assert len(result) == 1
    assert "richer description" in result[0].description


def test_dedupe_merges_fuzzy_titles():
    a = _opp("https://a.org/1", "Machine Learning Intern", "Ooredoo Algerie")
    b = _opp("https://b.org/2", "Machine  Learning  Intern!", "Ooredoo Algérie")
    assert len(dedupe([a, b])) == 1


def test_dedupe_keeps_distinct_opportunities():
    a = _opp("https://a.org/1", "ML Intern", "Ooredoo")
    b = _opp("https://b.org/2", "Robotics Engineer", "Boston Dynamics")
    assert len(dedupe([a, b])) == 2


def test_dedupe_keeps_latest_deadline():
    a = _opp("https://x.org/j", "Backend Dev", "Sarawak", deadline=date(2026, 11, 1))
    b = _opp("https://x.org/j", "Backend Dev", "Sarawak", deadline=date(2026, 12, 15))
    merged = dedupe([a, b])[0]
    assert merged.deadline == date(2026, 12, 15)


def test_similarity_identical_is_100():
    a = _opp("https://a.org", "Data Analyst Intern", "DP World")
    b = _opp("https://b.org", "Data Analyst Intern", "DP World")
    assert similarity(a, b) == 100
