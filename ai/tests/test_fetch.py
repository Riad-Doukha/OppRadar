# Fetch tests: User-Agent, status handling, robots.txt blocking, local
# fixture files — and the never-crash contract (errors become PageDoc.error).

import httpx

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.fetch import PageFetcher


def _settings(**updates):
    updates.setdefault("fetch_delay_seconds", 0.0)
    return get_settings().model_copy(update=updates)


def _fetcher(handler, **updates) -> PageFetcher:
    return PageFetcher(_settings(**updates), transport=httpx.MockTransport(handler))


def test_user_agent_and_200() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, text="<html><p>hello</p></html>")

    fetcher = _fetcher(handler, user_agent="TestBot/9.9")
    doc = fetcher.get("https://ua.test/page")
    assert doc.ok and doc.status == 200 and "hello" in doc.html
    assert doc.error == "" and doc.fetched_at is not None
    # robots.txt request + page request, both carrying the clear User-Agent
    assert len(seen) == 2 and set(seen) == {"TestBot/9.9"}


def test_404_is_an_error_not_an_exception() -> None:
    fetcher = _fetcher(lambda request: httpx.Response(404, text="gone"))
    doc = fetcher.get("https://nf.test/page")
    assert not doc.ok and doc.status == 404
    assert doc.error == "HTTP 404" and doc.html == ""


def test_network_error_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    doc = _fetcher(handler).get("https://down.test/page")
    assert not doc.ok and "connection refused" in doc.error


def test_local_fixture_file_is_read() -> None:
    from pathlib import Path

    sample = Path(__file__).resolve().parents[1] / "data" / "samples" / "page_scholarship.html"
    doc = PageFetcher(_settings()).get(str(sample))
    assert doc.ok and "Atlas Merit Scholarship" in doc.html


def test_missing_local_file_reports_error() -> None:
    doc = PageFetcher(_settings()).get("definitely/missing/page.html")
    assert not doc.ok and doc.error.startswith("local file not found")


def test_robots_disallow_blocks_before_any_request() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="<p>secret</p>")

    fetcher = _fetcher(handler)
    blocked = fetcher.get("https://r1.test/private/page")
    allowed = fetcher.get("https://r1.test/public/page")
    assert blocked.error == "blocked by robots.txt"
    assert allowed.ok
    assert "/private/page" not in paths  # never even requested
    assert "/robots.txt" in paths


def test_missing_robots_txt_allows_crawling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="<p>ok</p>")

    doc = _fetcher(handler).get("https://r2.test/news")
    assert doc.ok


def test_unreachable_robots_txt_allows_crawling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("no robots", request=request)
        return httpx.Response(200, text="<p>ok</p>")

    doc = _fetcher(handler).get("https://r3.test/news")
    assert doc.ok


def test_respect_robots_can_be_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="<p>ok</p>")

    doc = _fetcher(handler, respect_robots=False).get("https://r4.test/any")
    assert doc.ok
