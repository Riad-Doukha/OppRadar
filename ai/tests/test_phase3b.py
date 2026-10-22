# Phase 3b: the is_opportunity gate (listicles -> rejected, never stored),
# rule-first deadlines (a "Deadline:" line beats the model; a mismatch is
# flagged; Rolling/Varies stay null), body truncation, the capped optional
# detail fetch (live opt-in only — offline runs must never issue a request),
# list-page marking, and the frozen live-snapshot sanity.

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.clean import CleanedPage, looks_like_list_page
from oppradar_ai.ingestion.extract import (
    RawExtraction,
    deadline_line,
    extract_record,
    parse_deadline,
    to_opportunity,
    truncate_text,
)
from oppradar_ai.ingestion.fetch import PageDoc, PageFetcher
from oppradar_ai.ingestion.pipeline import _detail_fetch_allowed, run_ingestion
from oppradar_ai.schemas import (
    Opportunity,
    OpportunityExtraction,
    OpportunityType,
    Source,
)

AI_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = AI_ROOT / "data" / "eval"


def _settings(**updates):
    updates.setdefault("fetch_delay_seconds", 0.0)
    return get_settings().model_copy(update=updates)


def _extraction(**overrides) -> OpportunityExtraction:
    base = {
        "title": "Test Scholarship",
        "organizer": "Test Org",
        "type": OpportunityType.SCHOLARSHIP,
        "deadline": "March 15, 2027",
    }
    base.update(overrides)
    return OpportunityExtraction(**base)


# --------------------------------------------------------------------------- #
# is_opportunity gate
# --------------------------------------------------------------------------- #
def test_listicle_text_is_rejected_never_stored() -> None:
    """A 'Top 10 ...' headline is a listicle: rejected, kept out of opportunities."""
    outcome = extract_record(
        "Top 10 Scholarships in Netherlands for International Students",
        source_name="samples",
    )
    assert outcome.rejected_reason is not None
    assert outcome.opportunity is None  # never becomes an Opportunity record
    assert outcome.extraction is not None  # the raw model answer is still retained


def test_real_announcement_is_accepted() -> None:
    outcome = extract_record("Atlas Merit Scholarship 2027 is open.", source_name="t")
    assert outcome.rejected_reason is None
    assert isinstance(outcome.opportunity, Opportunity)


def test_extraction_schema_has_the_opportunity_gate() -> None:
    ext = _extraction(is_opportunity=False, not_opportunity_reason="news")
    assert ext.is_opportunity is False and ext.not_opportunity_reason == "news"


# --------------------------------------------------------------------------- #
# Rule-first deadlines
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Deadline: 30 November 2026", "30 November 2026"),
        ("Application Deadline: 30 November 2026.", "30 November 2026"),
        ("Date limite de candidature : 15 mars 2027", "15 mars 2027"),
        ("Date butoir : 2027-01-15", "2027-01-15"),
        ("deadline is 20 November 2028", "20 November 2028"),
        ("no explicit line here", ""),
    ],
)
def test_deadline_line_extracts_the_explicit_prefix(text: str, expected: str) -> None:
    assert deadline_line(text) == expected


def test_rule_deadline_beats_the_llm_and_flags_the_mismatch() -> None:
    """Model says 2027-03-15, source line says 2027-04-01 -> rule wins + note."""
    opp = to_opportunity(
        _extraction(deadline="March 15, 2027"),
        text="Deadline: 1 April 2027. Some scholarship body text.",
        url="https://example.org/s/1",
    )
    assert opp.deadline == date(2027, 4, 1)  # the rule value, not the model's
    assert opp.deadline_source == "rule"
    assert any("deadline mismatch" in n for n in opp.review_notes)
    deadline_fc = next(fc for fc in opp.field_confidences if fc.field == "deadline")
    assert deadline_fc.needs_review  # a disagreement is always "to verify"


def test_agreeing_rule_and_llm_do_not_flag_a_mismatch() -> None:
    opp = to_opportunity(
        _extraction(deadline="1 April 2027"),
        text="Deadline: 1 April 2027.",
        url="https://example.org/s/2",
    )
    assert opp.deadline == date(2027, 4, 1)
    assert not any("mismatch" in n for n in opp.review_notes)


@pytest.mark.parametrize(
    "phrase",
    ["Deadline: On Rolling Basis", "Deadline: Rolling Basis", "Deadline: Varies",
     "Deadline: Unspecified", "Deadline: Ongoing", "Date limite : en cours"],
)
def test_rolling_or_unspecified_stays_null_even_if_the_model_claims_a_date(
    phrase: str,
) -> None:
    opp = to_opportunity(
        _extraction(deadline="March 15, 2027"),
        text=f"{phrase}. Open all year.",
        url="https://example.org/s/3",
    )
    assert opp.deadline is None  # never invented, even against the model
    assert parse_deadline(phrase.split(":", 1)[1]) is None


def test_no_deadline_line_lets_the_llm_value_through() -> None:
    opp = to_opportunity(
        _extraction(deadline="March 15, 2027"),
        text="Applications are open now. Full details inside.",
        url="https://example.org/s/4",
    )
    assert opp.deadline == date(2027, 3, 15)
    assert opp.deadline_source == "llm"


# --------------------------------------------------------------------------- #
# Truncation
# --------------------------------------------------------------------------- #
def test_long_body_is_truncated_before_the_llm() -> None:
    long_body = "word " * 5000  # 25k chars
    assert len(truncate_text(long_body, 6000)) <= 6000 + len("\n[...truncated...]")
    assert truncate_text("short", 6000) == "short"


def test_truncate_text_marks_the_cut() -> None:
    out = truncate_text("x" * 20, 10)
    assert out.startswith("x" * 10) and "[...truncated...]" in out


# --------------------------------------------------------------------------- #
# List pages
# --------------------------------------------------------------------------- #
def test_list_page_marking_lowers_confidence_and_adds_note() -> None:
    opp = to_opportunity(
        _extraction(),
        url="https://example.org/jobs",
        list_page=True,
    )
    assert any("list page - needs detail" in n for n in opp.review_notes)
    assert all(fc.confidence <= 0.4 for fc in opp.field_confidences)
    assert all(fc.needs_review for fc in opp.field_confidences)


def test_looks_like_list_page_heuristic() -> None:
    links = [f"https://example.org/{i}" for i in range(30)]
    # EURAXESS-style jobs listing: many links + teaser-shaped (short) lines.
    teasers = "\n".join("Short teaser line here" for _ in range(20))
    assert looks_like_list_page(CleanedPage(text=teasers, links=links))
    # CampusFrance-style program page: huge nav but flowing prose -> not a list.
    prose = "\n".join(" ".join("word" for _ in range(20)) for _ in range(20))
    assert not looks_like_list_page(CleanedPage(text=prose, links=links))
    # A detail page or a local fixture never trips the heuristic.
    assert not looks_like_list_page(CleanedPage(text="a b c", links=[]))


# --------------------------------------------------------------------------- #
# Report counters + rejected routing (offline, fake LLM)
# --------------------------------------------------------------------------- #
def _feed(tmp_path: Path, items: list[tuple[str, str, str]]) -> Path:
    """Write a tiny RSS file: (title, link, description) tuples."""
    body = "\n".join(
        f"    <item><title>{t}</title><link>{u}</link>"
        f"<description><![CDATA[{d}]]></description></item>"
        for t, u, d in items
    )
    feed = tmp_path / "feed.xml"
    feed.write_text(
        f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
        f"{body}</channel></rss>",
        encoding="utf-8",
    )
    return feed


def test_pipeline_rejects_a_listicle_and_counts_it(tmp_path: Path) -> None:
    feed = _feed(tmp_path, [
        ("Atlas Real Scholarship", "https://example.org/a", "A real call, Deadline: 1 April 2027."),
        ("Top 10 Scholarships of 2026", "https://example.org/b", "Ranked listicle."),
    ])
    source = Source(name="t", url=str(feed), kind="rss")
    report = run_ingestion(sources=[source], settings=_settings())
    assert report.items_rejected == 1
    assert report.items_new == 1
    assert any("listicle" in r.reason for r in report.rejected)
    # the rejected item is NOT among the stored opportunities
    assert all("Top 10" not in o.title for o in report.opportunities)


def test_report_counts_deadline_provenance(tmp_path: Path) -> None:
    feed = _feed(tmp_path, [
        ("Rule Deadline Call", "https://example.org/r", "Deadline: 1 April 2027. Apply."),
    ])
    source = Source(name="t", url=str(feed), kind="rss")
    report = run_ingestion(sources=[source], settings=_settings())
    assert report.deadline_from_rule == 1
    assert report.deadline_null == 0


def test_report_schema_round_trips_with_new_fields(tmp_path: Path) -> None:
    feed = _feed(tmp_path, [("X", "https://example.org/x", "Deadline: 1 April 2027.")])
    report = run_ingestion(
        sources=[Source(name="t", url=str(feed), kind="rss")], settings=_settings()
    )
    from oppradar_ai.schemas import IngestionReport

    IngestionReport.model_validate(report.model_dump())


# --------------------------------------------------------------------------- #
# Optional detail fetch (capped)
# --------------------------------------------------------------------------- #
class _StubFetcher:
    """Serves a fixed ok PageDoc; records every URL it was asked for."""

    _DEFAULT_HTML = "<html><body><p>Deadline: 5 June 2027.</p></body></html>"

    def __init__(self, html: str = _DEFAULT_HTML) -> None:
        self.html = html
        self.calls: list[str] = []

    def get(self, url: str) -> PageDoc:
        self.calls.append(url)
        return PageDoc(url=url, ok=True, status=200, html=self.html,
                       fetched_at=datetime.now(timezone.utc))


def _accept_without_deadline(text: str, **kwargs) -> RawExtraction:
    """Extractor stub: every entry is accepted with NO deadline -> detail path."""
    opp = Opportunity(
        title="No Deadline", organizer="Org", type=OpportunityType.OTHER,
        deadline=None, url=kwargs.get("url", ""), source="t",
        field_confidences=[],
    )
    return RawExtraction(opportunity=opp, url=kwargs.get("url", ""))


def test_detail_fetch_is_capped_and_only_fills_missing_deadlines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _feed(tmp_path, [
        ("No Deadline A", "https://jobs.univ-annaba.dz/na", "Body with no date at all."),
        ("No Deadline B", "https://jobs.univ-annaba.dz/nb", "Body with no date at all."),
        ("No Deadline C", "https://jobs.univ-annaba.dz/nc", "Body with no date at all."),
    ])
    source = Source(name="t", url=str(feed), kind="rss")
    fetcher = _StubFetcher()
    # A live detail fetch needs the opt-in AND a real provider. The fetcher is
    # a stub and extract_record is replaced below: no request, no LLM call.
    settings = _settings(
        max_detail_fetches_per_run=2, llm_provider="ollama", run_live_llm=True
    )
    monkeypatch.setattr(
        "oppradar_ai.ingestion.pipeline.extract_record", _accept_without_deadline
    )
    report = run_ingestion(sources=[source], settings=settings, fetcher=fetcher)

    assert report.detail_fetches == 2  # capped at MAX_DETAIL_FETCHES_PER_RUN
    assert len(fetcher.calls) == 2  # only the cap's worth of detail pages fetched


@pytest.mark.parametrize("updates", [
    {},  # offline default: fake provider, no opt-in
    {"run_live_llm": True},  # opt-in alone is not enough (fake provider)
    {"llm_provider": "gemini", "run_live_llm": False},  # no opt-in either
])
def test_detail_fetch_never_touches_the_network_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, updates: dict
) -> None:
    """Fake provider or RUN_LIVE_LLM unset -> not a single HTTP request."""
    feed = _feed(tmp_path, [
        ("No Deadline A", "https://jobs.univ-annaba.dz/na", "Body with no date at all."),
        ("No Deadline B", "https://example.org/nb", "Body with no date at all."),
    ])
    source = Source(name="t", url=str(feed), kind="rss")

    def _no_http(*args, **kwargs):
        raise AssertionError("HTTP request attempted while offline")

    monkeypatch.setattr("httpx.Client.request", _no_http)
    monkeypatch.setattr(
        "oppradar_ai.ingestion.pipeline.extract_record", _accept_without_deadline
    )
    settings = _settings(**updates)
    report = run_ingestion(
        sources=[source], settings=settings, fetcher=PageFetcher(settings)
    )

    assert report.detail_fetches == 0
    assert report.failures == []  # a blocked fetch would surface here


def test_detail_fetch_refuses_placeholder_urls_even_when_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """example.org / local fixtures are never worth a request (they only 404)."""
    feed = _feed(tmp_path, [("No Deadline", "https://example.org/nd", "Body with no date.")])
    source = Source(name="t", url=str(feed), kind="rss")
    fetcher = _StubFetcher()
    monkeypatch.setattr(
        "oppradar_ai.ingestion.pipeline.extract_record", _accept_without_deadline
    )
    settings = _settings(llm_provider="gemini", run_live_llm=True)
    report = run_ingestion(sources=[source], settings=settings, fetcher=fetcher)

    assert fetcher.calls == []  # the placeholder URL was never requested
    assert report.detail_fetches == 0


@pytest.mark.parametrize("url,expected", [
    ("https://jobs.univ-annaba.dz/x", True),
    ("https://example.org/x", False),
    ("https://www.example.com/x", False),
    ("https://jobs.example.net/x", False),
    ("https://scholarship.test/x", False),
    ("/tmp/fixture_page.html", False),
])
def test_detail_fetch_gate_classifies_urls(url: str, expected: bool) -> None:
    live = _settings(llm_provider="gemini", run_live_llm=True)
    assert _detail_fetch_allowed(live, url) is expected


def test_detail_fetch_skipped_when_deadline_already_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _feed(tmp_path, [("Has Deadline", "https://example.org/hd", "Deadline: 1 April 2027.")])
    source = Source(name="t", url=str(feed), kind="rss")
    fetcher = _StubFetcher()
    report = run_ingestion(sources=[source], settings=_settings(), fetcher=fetcher)
    assert report.detail_fetches == 0
    assert fetcher.calls == []  # no pointless second fetch


# --------------------------------------------------------------------------- #
# Frozen live snapshot (committed eval data)
# --------------------------------------------------------------------------- #
def test_live_snapshot_is_well_formed() -> None:
    snapshot = EVAL_DIR / "live_snapshot.json"
    assert snapshot.exists(), "run scripts/snapshot_live.py to create it"
    import json

    data = json.loads(snapshot.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert len(entries) >= 12
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        assert {"id", "source", "title", "url", "summary", "fetched_at"} <= set(e)
        assert e["url"].startswith("http")


def test_live_labels_template_has_empty_fields() -> None:
    template = EVAL_DIR / "live_labels.template.json"
    assert template.exists()
    import json

    labels = json.loads(template.read_text(encoding="utf-8"))
    for row in labels.values():
        assert {"is_opportunity", "deadline", "type"} == set(row)
        assert row["is_opportunity"] is None
        assert row["deadline"] is None
        assert row["type"] is None


def test_extract_record_reports_provider_and_model() -> None:
    outcome = extract_record("Some scholarship text.", source_name="t")
    assert outcome.llm_provider and outcome.llm_model  # fake records itself
