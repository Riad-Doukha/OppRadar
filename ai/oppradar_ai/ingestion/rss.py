# RSS/Atom reading with feedparser: parse local fixtures or remote feeds.
# Broken feeds and I/O errors are returned as error strings (never raised).
# Called by: ingestion/pipeline.py, notebook 03_discovery.

from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
from pydantic import BaseModel

from oppradar_ai.ingestion.fetch import PageFetcher

logger = logging.getLogger(__name__)

_TAGS_RE = re.compile(r"<[^>]+>")


class FeedEntry(BaseModel):
    """One RSS/Atom item before page-level extraction."""

    title: str
    url: str
    summary: str = ""
    published: datetime | None = None


def parse_feed(content: str | bytes, source: str = "") -> tuple[list[FeedEntry], list[str]]:
    """Entries of a feed plus failure messages (empty errors = success).

    Example:
        >>> entries, errors = parse_feed("<rss><channel></channel></rss>", "x")
        >>> entries, len(errors)
        ([], 1)
    """
    name = source or "feed"
    try:
        feed = feedparser.parse(content)
    except Exception as exc:
        return [], [f"{name}: parse error: {exc}"]
    if not feed.entries:
        reason = str(getattr(feed, "bozo_exception", "")).strip() or "feed has no entries"
        logger.warning("%s: %s", name, reason)
        return [], [f"{name}: {reason}"]
    if getattr(feed, "bozo", False):
        logger.info("%s: recovered from a malformed feed (%s)", name, feed.bozo_exception)
    return [_entry(item) for item in feed.entries], []


def read_feed(
    location: str, fetcher: PageFetcher | None = None
) -> tuple[list[FeedEntry], list[str]]:
    """Read a feed from a local file path or an http(s) URL.

    Failures (missing file, HTTP error, broken XML) become error strings.
    """
    path = Path(location)
    if not path.exists() and not location.startswith(("http://", "https://")):
        return [], [f"{location}: local feed file not found"]
    if path.exists():
        try:
            return parse_feed(path.read_text(encoding="utf-8", errors="replace"), path.name)
        except OSError as exc:
            return [], [f"{location}: {exc}"]
    doc = (fetcher or PageFetcher()).get(location)
    if not doc.ok:
        return [], [f"{location}: {doc.error}"]
    return parse_feed(doc.html, location)


def _entry(item: dict) -> FeedEntry:
    summary = item.get("summary") or item.get("description") or ""
    return FeedEntry(
        title=str(item.get("title") or "").strip(),
        url=str(item.get("link") or "").strip(),
        summary=_strip_html(str(summary)),
        published=_published(item),
    )


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(_TAGS_RE.sub(" ", text))).strip()


def _published(item: dict) -> datetime | None:
    stamp = item.get("published_parsed") or item.get("updated_parsed")
    if not stamp:
        return None
    try:
        return datetime(*stamp[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
