# Tavily discovery with disk caching and a hard per-run cap: cache first,
# quota second, network last; failures are recorded as strings and never
# raised, so one bad search cannot crash a run. `cache_dir` lets demos and
# notebooks use a throwaway cache instead of the shared one.
# Called by: ingestion/pipeline.py, notebook 03_discovery.

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.llm import DiskCache, RateLimiter

logger = logging.getLogger(__name__)

ApiCall = Callable[[str, int], dict[str, Any]]


class SearchHit(BaseModel):
    """One search result (title + URL + snippet) before page fetching."""

    title: str
    url: str
    snippet: str = ""
    score: float = 0.0


class TavilySearcher:
    """Disk-capped Tavily client: never exceeds the run's search quota.

    Example:
        >>> searcher = TavilySearcher(api_call=lambda q, n: {"results": []})
        >>> isinstance(searcher.search("test query"), list)
        True
    """

    def __init__(
        self,
        settings: Settings | None = None,
        budget: RunBudget | None = None,
        api_call: ApiCall | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.budget = budget or RunBudget(self.settings)
        self.usage = self.budget.searches
        self.cache = DiskCache(cache_dir or self.settings.cache_dir / "tavily")
        self.limiter = RateLimiter(self.settings.llm_min_delay_seconds)
        self.api_call = api_call
        self.failures: list[str] = []

    def search(self, query: str, max_results: int | None = None) -> list[SearchHit]:
        """Results for `query`; returns [] and records a failure on any error."""
        max_results = max_results or self.settings.tavily_max_results
        key = self.cache.key("tavily", "v1", f"{query}|{max_results}")
        cached = self.cache.get(key)
        if cached is not None:
            self.usage.cached += 1
            logger.info("Tavily cache hit for %r", query)
            return [SearchHit.model_validate(row) for row in cached["hits"]]
        return self._live_search(query, max_results, key)

    # ------------------------------------------------------------------ #
    def _live_search(self, query: str, max_results: int, key: str) -> list[SearchHit]:
        if self.api_call is None and not self.settings.tavily_key_value:
            self.usage.skipped += 1
            return self._fail(f"no TAVILY_API_KEY; skipped search {query!r}")
        if not self.budget.allow_search():
            self.usage.skipped += 1
            logger.warning(
                "Tavily search limit (%d) reached; skipped %r", self.usage.limit, query
            )
            return []
        if self.api_call is None:
            self.limiter.wait()
        try:
            payload = (self.api_call or self._tavily_api)(query, max_results)
            hits = [self._to_hit(row) for row in payload.get("results") or []]
        except Exception as exc:  # a failing API must never kill a run
            return self._fail(f"Tavily search {query!r} failed: {exc}")
        self.cache.put(key, {"query": query, "hits": [h.model_dump() for h in hits]})
        logger.info("Tavily search %r -> %d hits", query, len(hits))
        return hits

    @staticmethod
    def _to_hit(row: dict[str, Any]) -> SearchHit:
        return SearchHit(
            title=str(row.get("title") or ""),
            url=str(row.get("url") or ""),
            snippet=str(row.get("content") or ""),
            score=float(row.get("score") or 0.0),
        )

    def _tavily_api(self, query: str, max_results: int) -> dict[str, Any]:
        from tavily import TavilyClient  # optional dep, only needed for live runs

        client = TavilyClient(api_key=self.settings.tavily_key_value)
        return client.search(query, max_results=max_results)

    def _fail(self, message: str) -> list[SearchHit]:
        logger.warning(message)
        self.failures.append(message)
        return []
