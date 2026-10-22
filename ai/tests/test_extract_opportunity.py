# Deadline normalization (ISO, never invented), per-field confidence with
# "to verify" marking, and the budgeted extract_from_text flow on fake LLM.

from datetime import date, datetime, timezone

import pytest

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.extract import (
    extract_from_text,
    find_deadline,
    opportunity_id,
    parse_deadline,
    to_opportunity,
)
from oppradar_ai.schemas import (
    FieldConfidence,
    Opportunity,
    OpportunityExtraction,
    OpportunityType,
)

DEADLINE_CASES = [
    ("15 March 2027", date(2027, 3, 15)),
    ("March 15, 2027", date(2027, 3, 15)),
    ("2027-03-15", date(2027, 3, 15)),
    ("30/11/2026", date(2026, 11, 30)),
    ("11/30/2026", date(2026, 11, 30)),  # US style when the first part > 12
    ("15 mars 2027", date(2027, 3, 15)),  # French month names
    ("Deadline: 30 October 2026!", date(2026, 10, 30)),  # embedded in a sentence
    # Ordinal day suffixes (EN st/nd/rd/th, FR er) are accepted and ignored
    ("3 November 2026", date(2026, 11, 3)),
    ("November 3rd, 2026", date(2026, 11, 3)),
    ("1st March 2027", date(2027, 3, 1)),
    ("May 1st, 2027", date(2027, 5, 1)),
    ("2nd April 2027", date(2027, 4, 2)),
    ("21st October 2026", date(2026, 10, 21)),
    ("22nd July 2027", date(2027, 7, 22)),
    ("23rd December 2026", date(2026, 12, 23)),
    ("May 5th 2027", date(2027, 5, 5)),
    ("1er mars 2027", date(2027, 3, 1)),  # French ordinal day
    ("Deadline: 15th June 2027", date(2027, 6, 15)),
    ("3rd", None),  # bare ordinal: a month/year is never invented
    ("1er", None),
    ("ongoing", None),
    ("present", None),
    ("current", None),
    ("rolling", None),
    ("open until filled", None),
    ("March 2027", None),  # month without a day: never invented
    ("", None),
    ("no date anywhere in this text", None),
    ("2027-02-30", None),  # impossible calendar date
]


@pytest.mark.parametrize("raw,expected", DEADLINE_CASES)
def test_parse_deadline_is_iso_and_never_invents(raw: str, expected) -> None:
    assert parse_deadline(raw) == expected


def test_find_deadline_scans_the_source_text() -> None:
    assert find_deadline("Applications close 30 October 2026. Go!") == "30 October 2026"
    assert find_deadline("Apply by 3rd November 2026!") == "3rd November 2026"
    assert find_deadline("cycle 2026, deadline 2027-03-15") == "2027-03-15"
    assert find_deadline("no dates in this text") == ""
    assert find_deadline("") == ""


def test_opportunity_id_is_deterministic() -> None:
    a = opportunity_id("Test Grant 2030", "https://example.org/x")
    assert a == opportunity_id("Test Grant 2030", "https://example.org/x")
    assert a != opportunity_id("Test Grant 2030", "https://example.org/y")
    assert a.startswith("test-grant-2030-")


def _extraction(**overrides) -> OpportunityExtraction:
    base = dict(
        title="Test Grant 2030",
        organizer="Test Org",
        type=OpportunityType.GRANT,
        deadline="15 March 2030",
        eligibility=["students"],
        benefits=["funding"],
        summary="A test grant.",
        field_confidences=[
            FieldConfidence(field="title", confidence=0.95),
            FieldConfidence(field="location", confidence=0.5),
        ],
    )
    base.update(overrides)
    return OpportunityExtraction(**base)


def test_to_opportunity_has_a_confidence_for_every_field() -> None:
    opp = to_opportunity(
        _extraction(),
        url="https://example.org/g/1",
        source_name="unit",
        source_checked=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    Opportunity.model_validate(opp.model_dump())  # schema validity of output
    assert opp.deadline == date(2030, 3, 15)  # ISO
    assert opp.id.startswith("test-grant-2030-")
    fields = {fc.field: fc for fc in opp.field_confidences}
    assert set(fields) == {
        "title", "organizer", "type", "location",
        "deadline", "eligibility", "benefits", "summary", "url",
    }
    assert not fields["title"].needs_review  # 0.95 >= threshold
    assert fields["location"].needs_review  # 0.5 < 0.65 -> "to verify"
    assert not fields["deadline"].needs_review
    assert all(0.0 <= fc.confidence <= 1.0 for fc in opp.field_confidences)


def test_missing_deadline_is_empty_and_flagged() -> None:
    opp = to_opportunity(_extraction(deadline=""), url="https://example.org/g/2")
    assert opp.deadline is None
    deadline_fc = next(fc for fc in opp.field_confidences if fc.field == "deadline")
    assert deadline_fc.needs_review  # absent deadline must be verified


def test_rolling_deadline_becomes_null() -> None:
    opp = to_opportunity(_extraction(deadline="ongoing"), url="https://example.org/g/3")
    assert opp.deadline is None


def test_unparseable_deadline_is_never_invented() -> None:
    opp = to_opportunity(
        _extraction(deadline="sometime next year hopefully"), url="https://example.org/g/4"
    )
    assert opp.deadline is None
    deadline_fc = next(fc for fc in opp.field_confidences if fc.field == "deadline")
    assert deadline_fc.confidence <= 0.2 and deadline_fc.needs_review


def test_rules_backfill_the_deadline_from_page_text() -> None:
    # Explicit "deadline is <date>" line -> rule-first path, confidence 0.9.
    opp = to_opportunity(
        _extraction(deadline=""),
        text="The application deadline is 20 November 2028.",
        url="https://example.org/g/5",
    )
    assert opp.deadline == date(2028, 11, 20)
    assert opp.deadline_source == "rule"
    deadline_fc = next(fc for fc in opp.field_confidences if fc.field == "deadline")
    assert deadline_fc.confidence == 0.9 and not deadline_fc.needs_review


def test_loose_date_scan_still_backfills_the_deadline() -> None:
    # No "Deadline:" prefix anywhere: the plain date scan keeps 0.75.
    opp = to_opportunity(
        _extraction(deadline=""),
        text="Applications close 20 November 2028. Apply early!",
        url="https://example.org/g/6",
    )
    assert opp.deadline == date(2028, 11, 20)
    deadline_fc = next(fc for fc in opp.field_confidences if fc.field == "deadline")
    assert deadline_fc.confidence == 0.75 and not deadline_fc.needs_review


def test_organizer_and_type_fall_back_without_inventing() -> None:
    opp = to_opportunity(
        _extraction(organizer="", type=OpportunityType.OTHER),
        type_hint=OpportunityType.SCHOLARSHIP,
        url="https://uni.example.dz/x",
    )
    assert opp.organizer == "uni.example.dz"  # host, flagged low below
    assert opp.type == OpportunityType.SCHOLARSHIP  # source type_hint used
    organizer_fc = next(fc for fc in opp.field_confidences if fc.field == "organizer")
    assert organizer_fc.needs_review


def test_blank_title_is_rejected_explicitly() -> None:
    with pytest.raises(ValueError):
        to_opportunity(_extraction(title=""), url="https://example.org/g/6")


def test_extract_from_text_end_to_end_on_fake_provider() -> None:
    budget = RunBudget(get_settings(), max_extractions=5)
    text = "e2e unique scholarship text about deadlines 15 March 2027 zz1"
    opp = extract_from_text(
        text, url="https://example.org/e2e-1", source_name="unit", budget=budget
    )
    assert opp is not None
    assert opp.title == "Atlas Merit Scholarship 2027"  # canned fake output
    assert opp.deadline == date(2027, 3, 15)  # canned raw string -> ISO
    assert opp.source == "unit" and opp.source_checked is not None
    assert budget.extractions.made == 1
    again = extract_from_text(
        text, url="https://example.org/e2e-1", source_name="unit", budget=budget
    )
    assert again is not None
    assert budget.extractions.cached == 1 and budget.extractions.made == 1  # free


def test_exhausted_budget_falls_back_to_rules_only() -> None:
    budget = RunBudget(get_settings(), max_extractions=1)
    first = extract_from_text(
        "budget unique text alpha 10 May 2029 qa1",
        url="https://example.org/b1",
        budget=budget,
    )
    second = extract_from_text(
        "budget unique text beta 11 May 2029 qa2",
        url="https://example.org/b2",
        budget=budget,
    )
    assert first is not None and second is not None
    assert budget.extractions.made == 1 and budget.extractions.skipped == 1
    assert all(fc.needs_review for fc in second.field_confidences)  # degraded
    assert second.deadline == date(2029, 5, 11)  # rules found it in the text


def test_failing_llm_never_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomLLM:
        @staticmethod
        def is_cached(*args, **kwargs) -> bool:
            return False

        @staticmethod
        def structured(*args, **kwargs):
            raise RuntimeError("provider down")

    monkeypatch.setattr("oppradar_ai.ingestion.extract.get_llm", lambda: BoomLLM())
    budget = RunBudget(get_settings(), max_extractions=3)
    opp = extract_from_text(
        "llm failure unique text 12 May 2029 qa3",
        url="https://example.org/boom",
        budget=budget,
    )
    assert opp is not None  # rules-only fallback, not an exception
    assert all(fc.needs_review for fc in opp.field_confidences)
    assert budget.extractions.made == 1  # the failed attempt still consumed quota
