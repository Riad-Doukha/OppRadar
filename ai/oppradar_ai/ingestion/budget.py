# Per-run hard caps on remote calls (free-tier protection): every Tavily
# search and every LLM extraction is gated here; disk-cache hits are free
# and always allowed. Called by: ingestion/search.py, ingestion/extract.py.

from __future__ import annotations

import statistics

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
        self.latencies: list[float] = []  # ms of the successful LLM calls (report p50)
        self.quota_exhausted = False  # set once a 429 is seen: stop calling the LLM

    def allow_search(self) -> bool:
        """Reserve quota for one real Tavily call (False once the cap is hit)."""
        return self._allow(self.searches)

    def allow_extraction(self) -> bool:
        """Reserve one LLM slot while made+failed_attempts sit under the cap.

        Unlike `allow_search` (a Tavily attempt is counted at once), the caller
        records the outcome with `record_extraction`, so `made` only ever counts
        successful responses and failures land in `failed_attempts`. A failed
        attempt still consumes its slot: a dead endpoint must not loop forever.
        """
        return self._spent(self.extractions) < self.extractions.limit

    def record_extraction(self, ok: bool) -> None:
        """Count one finished LLM call: a success in `made`, a failure otherwise."""
        if ok:
            self.extractions.made += 1
        else:
            self.extractions.failed_attempts += 1

    def note_latency(self, milliseconds: float) -> None:
        """Remember the latency of one successful LLM call (for the run report)."""
        if milliseconds > 0:
            self.latencies.append(milliseconds)

    def latency_p50_ms(self) -> float:
        """Median latency of the successful LLM calls (0.0 when there were none)."""
        return statistics.median(self.latencies) if self.latencies else 0.0

    @staticmethod
    def _allow(usage: CallUsage) -> bool:
        if usage.made >= usage.limit:
            return False
        usage.made += 1
        return True

    @staticmethod
    def _spent(usage: CallUsage) -> int:
        return usage.made + usage.failed_attempts
