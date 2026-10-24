# One ingestion run over the configured sources: fetch -> clean/parse ->
# budgeted extract (feed entries in BATCHES, is_opportunity gate, rule-first
# deadlines) -> dedupe by URL, collecting per-source stats, rejected items,
# deadline provenance, remote call usage and failures. NEVER raises: every
# problem becomes a failure entry in the returned IngestionReport.
# Called by: api.py (run_ingestion), agent.py, notebooks 03/04.

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.batch import BatchInput, extract_records_batch
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.clean import clean_html, looks_like_list_page
from oppradar_ai.ingestion.extract import (
    RawExtraction,
    extract_record,
    fields_filled,
    truncate_text,
)
from oppradar_ai.ingestion.fetch import PageFetcher
from oppradar_ai.ingestion.rss import FeedEntry, read_feed
from oppradar_ai.ingestion.search import TavilySearcher
from oppradar_ai.ingestion.sources import load_sources
from oppradar_ai.schemas import (
    CallUsage,
    IngestionReport,
    Opportunity,
    PendingLLMItem,
    RejectedItem,
    Source,
    SourceStats,
)

logger = logging.getLogger(__name__)


def run_ingestion(
    sources: list[Source] | None = None,
    settings: Settings | None = None,
    fetcher: PageFetcher | None = None,
    searcher: TavilySearcher | None = None,
) -> IngestionReport:
    """Ingest the enabled `sources` (default: sources.yaml) into a report.

    A failing source, page, feed or LLM call is logged and recorded in the
    report — the run itself always returns.

    Example:
        >>> report = run_ingestion(sources=[])
        >>> report.items_new, report.failures
        (0, [])
    """
    settings = settings or get_settings()
    started = datetime.now(timezone.utc)
    failures: list[str] = []
    sources = _resolve_sources(sources, settings, failures)
    budget = RunBudget(settings)
    fetcher = fetcher or PageFetcher(settings)
    searcher = searcher or TavilySearcher(settings, budget=budget)
    detail_usage = CallUsage(limit=settings.max_detail_fetches_per_run)
    opportunities: list[Opportunity] = []
    rejected: list[RejectedItem] = []
    pending: list[PendingLLMItem] = []  # no model answered -> retried next run
    stats: list[SourceStats] = []
    seen: set[str] = set()

    for source in sources:
        stat = SourceStats(source=source.name)
        start = time.monotonic()
        try:
            outcomes = _ingest_source(source, budget, fetcher, searcher, settings,
                                      stat, detail_usage)
        except Exception as exc:  # one broken source must not kill the run
            logger.exception("source %s failed", source.name)
            stat.errors.append(str(exc))
            outcomes = []
        stat.duration_seconds = round(time.monotonic() - start, 2)
        _collect(outcomes, source, stat, seen, opportunities, rejected, pending)
        failures.extend(f"{source.name}: {message}" for message in stat.errors)
        stats.append(stat)
    return _report(started, opportunities, stats, failures, budget,
                   searcher.usage, rejected, pending, detail_usage)


def _resolve_sources(
    sources: list[Source] | None,
    settings: Settings,
    failures: list[str],
) -> list[Source]:
    if sources is not None:
        return [s for s in sources if s.enabled]
    try:
        return [s for s in load_sources(settings.sources_path) if s.enabled]
    except Exception as exc:  # a broken yaml must not crash the run
        logger.error("cannot load sources.yaml: %s", exc)
        failures.append(f"sources.yaml: {exc}")
        return []


# --------------------------------------------------------------------------- #
# Per-source ingestion
# --------------------------------------------------------------------------- #
def _ingest_source(
    source: Source,
    budget: RunBudget,
    fetcher: PageFetcher,
    searcher: TavilySearcher,
    settings: Settings,
    stat: SourceStats,
    detail_usage: CallUsage,
) -> list[RawExtraction]:
    """One source -> extraction outcomes; errors go to `stat`, never raised."""
    if source.kind == "rss":
        entries, errors = read_feed(source.url, fetcher)
        stat.errors.extend(errors)
        stat.fetched = len(entries)
        outcomes = extract_records_batch(
            [_entry_input(entry, source, settings) for entry in entries],
            budget=budget,
            settings=settings,
        )
        for entry, outcome in zip(entries, outcomes, strict=True):
            _fill_deadline_from_detail(
                outcome, entry, source, budget, settings, fetcher, detail_usage
            )
        return outcomes
    if source.kind == "page":
        return _from_page(source, budget, fetcher, settings, stat)
    return _from_search(source, budget, fetcher, searcher, settings, stat)


def _entry_input(entry: FeedEntry, source: Source, settings: Settings) -> BatchInput:
    """One feed entry -> batch input (title+summary, capped to the feed limit)."""
    return BatchInput(
        text=truncate_text(f"{entry.title}\n{entry.summary}", settings.feed_text_max_chars),
        url=entry.url,
        source_name=source.name,
        title_hint=entry.title,
        type_hint=source.type_hint,
        language=source.language,
        country=source.country,
    )


def live_fetch_allowed(settings: Settings, url: str) -> bool:
    """May a single URL be fetched live (detail page, api.extract_opportunity)?

    Offline runs must never touch the network: the fake provider has
    nothing to re-extract with, and without the RUN_LIVE_LLM=1 opt-in no
    remote call is ever intended. Placeholder URLs (local fixtures,
    example.org) are also refused — they can only cost a request and a 404.

    Example:
        >>> live = Settings(llm_provider="gemini", run_live_llm=True)
        >>> live_fetch_allowed(live, "https://example.org/job/1")
        False
        >>> live_fetch_allowed(Settings(llm_provider="fake", run_live_llm=True),
        ...                    "https://host.tld/job/1")
        False
        >>> live_fetch_allowed(live, "https://host.tld/job/1")
        True
    """
    if settings.llm_provider == "fake" or not settings.run_live_llm:
        return False
    return not _placeholder_url(url)


def _placeholder_url(url: str) -> bool:
    """Local paths, example.* hosts and reserved TLDs (.test/.invalid/...)."""
    if not url.startswith(("http://", "https://")):
        return True
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    root = ".".join(host.split(".")[-2:])
    if root in {"example.org", "example.com", "example.net"}:
        return True
    return host.endswith((".test", ".example", ".invalid", ".localhost", ".local"))


def _fill_deadline_from_detail(
    outcome: RawExtraction,
    entry: FeedEntry,
    source: Source,
    budget: RunBudget,
    settings: Settings,
    fetcher: PageFetcher,
    detail_usage: CallUsage,
) -> None:
    """Accepted entry without a deadline -> one capped detail-page re-extract."""
    if outcome.opportunity is None or outcome.opportunity.deadline is not None:
        return
    if not live_fetch_allowed(settings, entry.url):
        logger.info("detail fetch skipped (offline): %s", entry.url)
        detail_usage.skipped += 1  # declined on purpose, not by budget
        return
    if detail_usage.made >= detail_usage.limit:  # hard cap (free-tier protection)
        return
    detail_usage.made += 1
    doc = fetcher.get(entry.url)
    if not doc.ok:
        logger.info("detail fetch skipped for %s: %s", entry.url, doc.error)
        return
    page = clean_html(doc.html, entry.url)
    retry = extract_record(
        truncate_text(page.text, settings.llm_max_input_chars),
        url=entry.url,
        source_name=source.name,
        title_hint=page.title or entry.title,
        type_hint=source.type_hint,
        language=source.language,
        country=source.country,
        budget=budget,
        settings=settings,
        list_page=looks_like_list_page(page),
    )
    if retry.opportunity is not None and retry.opportunity.deadline is not None:
        retry.opportunity.review_notes.append("deadline filled from the detail page")
        outcome.opportunity = retry.opportunity


def _from_page(
    source: Source,
    budget: RunBudget,
    fetcher: PageFetcher,
    settings: Settings,
    stat: SourceStats,
) -> list[RawExtraction]:
    doc = fetcher.get(source.url)
    if not doc.ok:
        stat.errors.append(doc.error)
        return []
    stat.fetched = 1
    page = clean_html(doc.html, source.url)
    is_list = looks_like_list_page(page)
    if is_list:
        stat.list_pages += 1
    return [
        extract_record(
            page.text,
            url=page.canonical or source.url,
            source_name=source.name,
            title_hint=page.title,
            type_hint=source.type_hint,
            language=source.language,
            country=source.country,
            budget=budget,
            settings=settings,
            list_page=is_list,
        )
    ]


def _from_search(
    source: Source,
    budget: RunBudget,
    fetcher: PageFetcher,
    searcher: TavilySearcher,
    settings: Settings,
    stat: SourceStats,
) -> list[RawExtraction]:
    # For kind="search" the `url` field carries the Tavily query string.
    before = len(searcher.failures)
    hits = searcher.search(source.url)
    stat.errors.extend(searcher.failures[before:])
    stat.fetched += len(hits)
    outcomes: list[RawExtraction] = []
    for hit in hits:
        doc = fetcher.get(hit.url)
        if not doc.ok:
            stat.errors.append(f"{hit.url}: {doc.error}")
            continue
        page = clean_html(doc.html, hit.url)
        is_list = looks_like_list_page(page)
        if is_list:
            stat.list_pages += 1
        outcomes.append(
            extract_record(
                page.text,
                url=page.canonical or hit.url,
                source_name=source.name,
                title_hint=page.title,
                type_hint=source.type_hint,
                language=source.language,
                country=source.country,
                budget=budget,
                settings=settings,
                list_page=is_list,
            )
        )
    return outcomes


# --------------------------------------------------------------------------- #
# Collect + dedupe
# --------------------------------------------------------------------------- #
def _collect(
    outcomes: list[RawExtraction],
    source: Source,
    stat: SourceStats,
    seen: set[str],
    opportunities: list[Opportunity],
    rejected: list[RejectedItem],
    pending: list[PendingLLMItem],
) -> None:
    """Split outcomes into rejected items, pending LLM items and opportunities."""
    for outcome in outcomes:
        if outcome.pending is not None:
            stat.pending += 1
            pending.append(outcome.pending)
            continue
        if outcome.rejected_reason is not None:
            stat.rejected += 1
            rejected.append(
                RejectedItem(
                    source=source.name,
                    title=(outcome.extraction.title.strip() if outcome.extraction else "")
                    or "(no title)",
                    url=outcome.url,
                    reason=outcome.rejected_reason,
                )
            )
            continue
        _dedupe_one(outcome.opportunity, seen, stat, opportunities)


def _dedupe_one(
    opp: Opportunity | None,
    seen: set[str],
    stat: SourceStats,
    opportunities: list[Opportunity],
) -> None:
    """Drop cross-source duplicates (same normalized URL); fill `stat`."""
    if opp is None:
        stat.errors.append("item without a usable title was skipped")
        return
    stat.extracted += 1
    key = (opp.url.rstrip("/") or opp.id).lower()
    if key in seen:
        stat.duplicates += 1
        return
    seen.add(key)
    stat.new += 1
    stat.fields_filled += fields_filled(opp)
    opportunities.append(opp)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _report(
    started: datetime,
    opportunities: list[Opportunity],
    stats: list[SourceStats],
    failures: list[str],
    budget: RunBudget,
    search_usage: CallUsage,
    rejected: list[RejectedItem],
    pending: list[PendingLLMItem],
    detail_usage: CallUsage,
) -> IngestionReport:
    deadlines = _deadline_counts(opportunities)
    report = IngestionReport(
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        opportunities=opportunities,
        per_source=stats,
        items_fetched=sum(s.fetched for s in stats),
        items_new=sum(s.new for s in stats),
        items_duplicate=sum(s.duplicates for s in stats),
        items_flagged=sum(1 for opp in opportunities if opp.to_verify()),
        items_rejected=len(rejected),
        items_list_pages=sum(s.list_pages for s in stats),
        deadline_from_rule=deadlines["rule"],
        deadline_from_llm=deadlines["llm"],
        deadline_mismatches=deadlines["mismatch"],
        deadline_null=deadlines["null"],
        detail_fetches=detail_usage.made,
        searches=search_usage,
        extractions=budget.extractions,
        extraction_p50_latency_ms=budget.latency_p50_ms(),
        rejected=rejected,
        pending_llm=pending,
        failures=failures,
    )
    logger.info(
        "ingestion finished: %d new / %d fetched from %d source(s) | "
        "accepted %d / rejected %d / flagged %d / pending %d | deadlines rule %d llm %d "
        "mismatch %d null %d | detail fetches %d (%d declined offline) | "
        "Tavily %d made / %d cached / %d skipped (cap %d) | "
        "LLM %d made / %d failed / %d cached / %d skipped (cap %d) | p50 %.0f ms | "
        "%d failure(s)",
        report.items_new, report.items_fetched, len(stats),
        report.items_new, report.items_rejected, report.items_flagged,
        len(report.pending_llm),
        report.deadline_from_rule, report.deadline_from_llm,
        report.deadline_mismatches, report.deadline_null, report.detail_fetches,
        detail_usage.skipped,
        report.searches.made, report.searches.cached, report.searches.skipped,
        report.searches.limit,
        report.extractions.made, report.extractions.failed_attempts,
        report.extractions.cached, report.extractions.skipped,
        report.extractions.limit, report.extraction_p50_latency_ms,
        len(report.failures),
    )
    return report


def _deadline_counts(opportunities: list[Opportunity]) -> dict[str, int]:
    """Per-run deadline provenance: rule vs llm vs mismatch vs null."""
    return {
        "rule": sum(
            1 for o in opportunities
            if o.deadline is not None and o.deadline_source == "rule"
        ),
        "llm": sum(
            1 for o in opportunities
            if o.deadline is not None and o.deadline_source == "llm"
        ),
        "mismatch": sum(
            1 for o in opportunities if any("mismatch" in n for n in o.review_notes)
        ),
        "null": sum(1 for o in opportunities if o.deadline is None),
    }
