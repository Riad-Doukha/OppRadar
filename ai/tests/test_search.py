# Search tests: disk caching, the hard per-run cap, missing-key skips and
# the never-crash contract for the Tavily discovery client.

import json
from pathlib import Path

from pydantic import SecretStr

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.search import TavilySearcher

SAMPLE = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "samples" / "tavily_response_sample.json")
    .read_text(encoding="utf-8")
)


def _settings(**updates):
    return get_settings().model_copy(update=updates)


def test_search_parses_hits_and_counts_the_call() -> None:
    calls: list[str] = []

    def api(query: str, max_results: int) -> dict:
        calls.append(query)
        return SAMPLE

    searcher = TavilySearcher(_settings(), api_call=api)
    hits = searcher.search("unique parse test query")
    assert len(hits) == 3
    assert hits[0].title.startswith("Atlas Merit Scholarship")
    assert hits[0].url == "https://example.org/atlas-merit-scholarship-2027"
    assert hits[0].score > 0.8 and hits[0].snippet
    assert searcher.usage.made == 1 and searcher.usage.cached == 0
    assert calls == ["unique parse test query"]


def test_second_identical_search_is_a_free_cache_hit() -> None:
    calls: list[str] = []

    def api(query: str, max_results: int) -> dict:
        calls.append(query)
        return SAMPLE

    searcher = TavilySearcher(_settings(), api_call=api)
    searcher.search("unique cache test query")
    again = searcher.search("unique cache test query")
    assert len(again) == 3
    assert searcher.usage.made == 1 and searcher.usage.cached == 1
    assert len(calls) == 1  # the API was hit exactly once


def test_per_run_limit_blocks_extra_searches() -> None:
    settings = _settings(tavily_max_searches_per_run=1)
    searcher = TavilySearcher(settings, budget=RunBudget(settings), api_call=lambda q, n: SAMPLE)
    assert len(searcher.search("unique limited query one")) == 3
    assert searcher.search("unique limited query two") == []
    assert searcher.usage.made == 1
    assert searcher.usage.skipped == 1 and searcher.usage.limit == 1
    assert searcher.failures == []  # hitting a cap is not a failure


def test_failing_api_is_recorded_and_never_raises() -> None:
    def api(query: str, max_results: int) -> dict:
        raise RuntimeError("tavily is down")

    searcher = TavilySearcher(_settings(), api_call=api)
    assert searcher.search("unique failing query") == []
    assert searcher.failures and "tavily is down" in searcher.failures[0]
    assert searcher.usage.made == 1


def test_missing_key_skips_without_network() -> None:
    settings = _settings(tavily_api_key=SecretStr(""))
    searcher = TavilySearcher(settings)  # no api_call -> would need a real key
    assert searcher.search("unique no key query") == []
    assert searcher.usage.skipped == 1 and searcher.usage.made == 0
    assert "no TAVILY_API_KEY" in searcher.failures[0]


def test_cache_dir_override_keeps_demo_queries_out_of_the_shared_cache(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def api(query: str, max_results: int) -> dict:
        calls.append(query)
        return SAMPLE

    demo = tmp_path / "demo_tavily"
    first = TavilySearcher(_settings(), api_call=api, cache_dir=demo)
    first.search("unique isolated demo query")
    assert first.usage.made == 1 and len(calls) == 1

    second = TavilySearcher(_settings(), api_call=api, cache_dir=demo)
    second.search("unique isolated demo query")
    assert second.usage.cached == 1 and len(calls) == 1  # shares the demo cache

    shared = TavilySearcher(_settings(), api_call=api)
    shared.search("unique isolated demo query")
    assert shared.usage.made == 1 and len(calls) == 2  # demo cache stayed private
