# ingestion/ — discovery, fetching and extraction of opportunities from
# real public sources (RSS feeds, pages, Tavily search), with free-tier
# budgets, robots.txt politeness and never-crash reporting.

from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.clean import CleanedPage, clean_html
from oppradar_ai.ingestion.extract import (
    extract_from_text,
    fields_filled,
    find_deadline,
    opportunity_id,
    parse_deadline,
    to_opportunity,
)
from oppradar_ai.ingestion.fetch import PageDoc, PageFetcher
from oppradar_ai.ingestion.pipeline import run_ingestion
from oppradar_ai.ingestion.robots import origin_of, parse_robots, robots_allows
from oppradar_ai.ingestion.rss import FeedEntry, parse_feed, read_feed
from oppradar_ai.ingestion.search import SearchHit, TavilySearcher
from oppradar_ai.ingestion.sources import load_sources

__all__ = [
    "CleanedPage",
    "FeedEntry",
    "PageDoc",
    "PageFetcher",
    "RunBudget",
    "SearchHit",
    "TavilySearcher",
    "clean_html",
    "extract_from_text",
    "fields_filled",
    "find_deadline",
    "load_sources",
    "opportunity_id",
    "origin_of",
    "parse_deadline",
    "parse_feed",
    "parse_robots",
    "read_feed",
    "robots_allows",
    "run_ingestion",
    "to_opportunity",
]
