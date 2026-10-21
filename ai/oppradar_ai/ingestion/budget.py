# Per-run hard caps on remote calls (free-tier protection): every Tavily
# search and every LLM extraction is gated here; disk-cache hits are free
# and always allowed. Called by: ingestion/search.py, ingestion/extract.py.

from __future__ import annotations

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.schemas import CallUsage


class RunBudget:
    """Hard per-run quotas for remote calls; cache hits never consume quota.

    A quota of 0 blocks every real call (used by offline tests).

    Example:
        >>> budget = RunBudget(max_searches=1, max_extractions=0)
        >>> budget.allow_search(), budget.allow_search()
        (True, False)
        >>> budget.allow_extraction()
        False
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_searches: int | None = None,
        max_extractions: int | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.searches = CallUsage(
            limit=settings.tavily_max_searches_per_run if max_searches is None else max_searches
        )
        self.extractions = CallUsage(
            limit=settings.max_extractions_per_run if max_extractions is None else max_extractions
        )

    def allow_search(self) -> bool:
        """Reserve quota for one real Tavily call (False once the cap is hit)."""
        return self._allow(self.searches)

    def allow_extraction(self) -> bool:
        """Reserve quota for one real LLM extraction call (False at the cap)."""
        return self._allow(self.extractions)

    @staticmethod
    def _allow(usage: CallUsage) -> bool:
        if usage.made >= usage.limit:
            return False
        usage.made += 1
        return True
