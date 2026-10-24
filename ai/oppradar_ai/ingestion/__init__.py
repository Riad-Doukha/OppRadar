# ingestion/ — discovery, fetching and extraction of opportunities from
# real public sources (RSS feeds, pages, Tavily search), with free-tier
# budgets, robots.txt politeness and never-crash reporting.

from oppradar_ai.ingestion.batch import BatchInput, extract_records_batch
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.clean import CleanedPage, clean_html, looks_like_list_page
from oppradar_ai.ingestion.extract import (
    RawExtraction,
    budgeted_structured,
    deadline_line,
    extract_from_text,
    extract_record,
    fields_filled,
    find_deadline,
    llm_identity,
    opportunity_id,
    outcome_from_extraction,
    parse_deadline,
    to_opportunity,
    truncate_text,
)
from oppradar_ai.ingestion.fetch import PageDoc, PageFetcher
from oppradar_ai.ingestion.pipeline import live_fetch_allowed, run_ingestion
from oppradar_ai.ingestion.robots import origin_of, parse_robots, robots_allows
from oppradar_ai.ingestion.rss import FeedEntry, parse_feed, read_feed
from oppradar_ai.ingestion.search import SearchHit, TavilySearcher
from oppradar_ai.ingestion.sources import load_sources

__all__ = [
    "BatchInput",
    "CleanedPage",
    "FeedEntry",
    "PageDoc",
    "PageFetcher",
    "RawExtraction",
    "RunBudget",
    "SearchHit",
    "TavilySearcher",
    "budgeted_structured",
    "clean_html",
    "deadline_line",
    "extract_from_text",
    "extract_record",
    "extract_records_batch",
    "fields_filled",
    "find_deadline",
    "live_fetch_allowed",
    "llm_identity",
    "load_sources",
    "looks_like_list_page",
    "opportunity_id",
    "origin_of",
    "outcome_from_extraction",
    "parse_deadline",
    "parse_feed",
    "parse_robots",
    "read_feed",
    "robots_allows",
    "run_ingestion",
    "to_opportunity",
    "truncate_text",
]
