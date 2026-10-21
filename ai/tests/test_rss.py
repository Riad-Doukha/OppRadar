# RSS tests: sample feed parsing (entries, dates, HTML-stripped summaries),
# local-file reading, and broken feeds becoming error strings, never raises.

from datetime import datetime, timezone
from pathlib import Path

from oppradar_ai.ingestion.rss import parse_feed, read_feed

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
FEED = SAMPLES / "feed_opportunities.xml"


def test_sample_feed_parses_three_entries() -> None:
    entries, errors = parse_feed(FEED.read_text(encoding="utf-8"), "sample")
    assert errors == []
    assert len(entries) == 3
    assert entries[0].title.startswith("Green Shield Research Fellowship")
    assert entries[0].url == "https://example.org/fellowships/green-shield-2027"
    assert entries[0].published == datetime(2026, 10, 19, 8, 30, tzinfo=timezone.utc)


def test_summaries_are_html_stripped() -> None:
    entries, _ = parse_feed(FEED.read_text(encoding="utf-8"), "sample")
    assert "<strong>" not in entries[1].summary
    assert "ongoing" in entries[1].summary  # text kept, tags removed
    assert "No deadline is published" in entries[2].summary


def test_read_feed_from_local_path() -> None:
    entries, errors = read_feed(str(FEED))
    assert errors == [] and len(entries) == 3


def test_missing_local_feed_is_an_error_string() -> None:
    entries, errors = read_feed(str(SAMPLES / "does_not_exist.xml"))
    assert entries == [] and "local feed file not found" in errors[0]


def test_broken_feed_never_raises() -> None:
    for junk in ("this is not xml at all", "<rss><channel>", ""):
        entries, errors = parse_feed(junk, "broken")
        assert entries == []
        assert len(errors) == 1 and errors[0].startswith("broken")
