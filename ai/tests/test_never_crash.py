# Never-crash contract for whole runs: broken sources, a failing search
# provider and a broken sources.yaml all become report failures — the
# pipeline itself always returns a schema-valid IngestionReport.

from pathlib import Path

from pydantic import SecretStr

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.pipeline import run_ingestion
from oppradar_ai.ingestion.search import TavilySearcher
from oppradar_ai.schemas import IngestionReport, Source

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def _settings(**updates):
    updates.setdefault("fetch_delay_seconds", 0.0)
    return get_settings().model_copy(update=updates)


def _raising_searcher(settings) -> TavilySearcher:
    def api(query: str, max_results: int) -> dict:
        raise RuntimeError("search provider down")

    return TavilySearcher(settings, api_call=api)


def test_broken_sources_produce_a_valid_report() -> None:
    settings = _settings(tavily_api_key=SecretStr(""))
    sources = [
        Source(name="missing-feed", url=str(SAMPLES / "nope.xml"), kind="rss"),
        Source(name="missing-page", url=str(SAMPLES / "nope.html"), kind="page"),
        Source(name="dead-search", url="unique broken search query zz9", kind="search"),
    ]
    report = run_ingestion(
        sources=sources, settings=settings, searcher=_raising_searcher(settings)
    )
    assert isinstance(report, IngestionReport)
    IngestionReport.model_validate(report.model_dump())  # round-trip validity
    assert report.items_new == 0
    assert len(report.failures) == 3  # one failure recorded per source
    assert any("local feed file not found" in f for f in report.failures)
    assert any("local file not found" in f for f in report.failures)
    assert any("search provider down" in f for f in report.failures)
    stats = {s.source: s for s in report.per_source}
    assert stats["missing-feed"].errors
    assert stats["dead-search"].errors
    assert report.searches.made == 1  # the failed attempt is still accounted


def test_missing_yaml_does_not_crash(tmp_path: Path) -> None:
    report = run_ingestion(settings=_settings(data_dir=tmp_path))
    assert report.failures and report.failures[0].startswith("sources.yaml")
    assert report.items_new == 0
    assert report.per_source == []


def test_malformed_yaml_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "sources.yaml").write_text(
        "sources: [broken: yaml: entries", encoding="utf-8"
    )
    report = run_ingestion(settings=_settings(data_dir=tmp_path))
    assert report.failures and report.failures[0].startswith("sources.yaml")
    assert report.items_new == 0


def test_disabled_sources_are_skipped(tmp_path: Path) -> None:
    settings = _settings(data_dir=tmp_path, tavily_api_key=SecretStr(""))
    sources = [
        Source(
            name="off-feed",
            url=str(SAMPLES / "feed_opportunities.xml"),
            kind="rss",
            enabled=False,
        ),
    ]
    report = run_ingestion(sources=sources, settings=settings)
    assert report.per_source == [] and report.items_new == 0
    assert report.failures == []
