# One ingestion run over the configured sources: fetch -> clean/parse ->
# budgeted extract -> dedupe by URL, collecting per-source stats, remote
# call usage and failures. NEVER raises: every problem becomes a failure
# entry in the returned IngestionReport.
# Called by: api.py (Phase 7), notebooks 03_discovery / 04_page_extraction.

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.clean import clean_html
from oppradar_ai.ingestion.extract import extract_from_text, fields_filled
from oppradar_ai.ingestion.fetch import PageFetcher
from oppradar_ai.ingestion.rss import FeedEntry, read_feed
from oppradar_ai.ingestion.search import TavilySearcher
from oppradar_ai.ingestion.sources import load_sources
from oppradar_ai.schemas import CallUsage, IngestionReport, Opportunity, Source, SourceStats

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
    opportunities: list[Opportunity] = []
    stats: list[SourceStats] = []
    seen: set[str] = set()

    for source in sources:
        stat = SourceStats(source=source.name)
        start = time.monotonic()
        try:
            found = _ingest_source(source, budget, fetcher, searcher, seen, settings, stat)
        except Exception as exc:  # one broken source must not kill the run
            logger.exception("source %s failed", source.name)
            stat.errors.append(str(exc))
            found = []
        stat.duration_seconds = round(time.monotonic() - start, 2)
        opportunities.extend(found)
        failures.extend(f"{source.name}: {message}" for message in stat.errors)
        stats.append(stat)
    return _report(
        started, opportunities, stats, failures, budget, searcher.usage
    )


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
    seen: set[str],
    settings: Settings,
    stat: SourceStats,
) -> list[Opportunity]:
    """One source -> fresh (deduped) opportunities; errors go to `stat`."""
    if source.kind == "rss":
        entries, errors = read_feed(source.url, fetcher)
        stat.errors.extend(errors)
        stat.fetched = len(entries)
        found = [_from_entry(entry, source, budget, settings) for entry in entries]
    elif source.kind == "page":
        found = _from_page(source, budget, fetcher, settings, stat)
    else:
        found = _from_search(source, budget, fetcher, searcher, settings, stat)
    return _dedupe(found, seen, stat)


def _from_entry(
    entry: FeedEntry, source: Source, budget: RunBudget, settings: Settings
) -> Opportunity | None:
    return extract_from_text(
        f"{entry.title}\n{entry.summary}",
        url=entry.url,
        source_name=source.name,
        title_hint=entry.title,
        type_hint=source.type_hint,
        language=source.language,
        country=source.country,
        budget=budget,
        settings=settings,
    )


def _from_page(
    source: Source,
    budget: RunBudget,
    fetcher: PageFetcher,
    settings: Settings,
    stat: SourceStats,
) -> list[Opportunity | None]:
    doc = fetcher.get(source.url)
    if not doc.ok:
        stat.errors.append(doc.error)
        return []
    stat.fetched = 1
    page = clean_html(doc.html, source.url)
    opp = extract_from_text(
        page.text,
        url=page.canonical or source.url,
        source_name=source.name,
        title_hint=page.title,
        type_hint=source.type_hint,
        language=source.language,
        country=source.country,
        budget=budget,
        settings=settings,
    )
    return [opp]


def _from_search(
    source: Source,
    budget: RunBudget,
    fetcher: PageFetcher,
    searcher: TavilySearcher,
    settings: Settings,
    stat: SourceStats,
) -> list[Opportunity | None]:
    # For kind="search" the `url` field carries the Tavily query string.
    before = len(searcher.failures)
    hits = searcher.search(source.url)
    stat.errors.extend(searcher.failures[before:])
    stat.fetched += len(hits)
    found: list[Opportunity | None] = []
    for hit in hits:
        doc = fetcher.get(hit.url)
        if not doc.ok:
            stat.errors.append(f"{hit.url}: {doc.error}")
            continue
        page = clean_html(doc.html, hit.url)
        found.append(
            extract_from_text(
                page.text,
                url=page.canonical or hit.url,
                source_name=source.name,
                title_hint=page.title,
                type_hint=source.type_hint,
                language=source.language,
                country=source.country,
                budget=budget,
                settings=settings,
            )
        )
    return found


def _dedupe(
    found: list[Opportunity | None], seen: set[str], stat: SourceStats
) -> list[Opportunity]:
    """Drop cross-source duplicates (same normalized URL); fill `stat`."""
    fresh: list[Opportunity] = []
    for opp in found:
        if opp is None:
            stat.errors.append("item without a usable title was skipped")
            continue
        stat.extracted += 1
        key = (opp.url.rstrip("/") or opp.id).lower()
        if key in seen:
            stat.duplicates += 1
            continue
        seen.add(key)
        stat.new += 1
        stat.fields_filled += fields_filled(opp)
        fresh.append(opp)
    return fresh


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
) -> IngestionReport:
    report = IngestionReport(
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        opportunities=opportunities,
        per_source=stats,
        items_fetched=sum(s.fetched for s in stats),
        items_new=sum(s.new for s in stats),
        items_duplicate=sum(s.duplicates for s in stats),
        items_flagged=sum(1 for opp in opportunities if opp.to_verify()),
        searches=search_usage,
        extractions=budget.extractions,
        failures=failures,
    )
    logger.info(
        "ingestion finished: %d new / %d fetched from %d source(s) | "
        "Tavily %d made / %d cached / %d skipped (cap %d) | "
        "LLM %d made / %d cached / %d skipped (cap %d) | %d failure(s)",
        report.items_new, report.items_fetched, len(stats),
        report.searches.made, report.searches.cached, report.searches.skipped,
        report.searches.limit,
        report.extractions.made, report.extractions.cached, report.extractions.skipped,
        report.extractions.limit, len(report.failures),
    )
    return report
