# Polite HTTP fetching: clear User-Agent, timeout, delay between requests,
# robots.txt enforcement (disk-cached per origin, 24 h TTL). Returns a
# result object instead of raising, so a failing URL never crashes a run.
# Called by: ingestion/pipeline.py, ingestion/rss.py, notebooks 03/04.

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import BaseModel

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.robots import origin_of, robots_allows
from oppradar_ai.llm import DiskCache, RateLimiter

logger = logging.getLogger(__name__)

_ROBOTS_TTL = 24 * 3600.0  # re-fetch robots.txt at most once a day


class PageDoc(BaseModel):
    """Outcome of one fetch attempt (never an exception)."""

    url: str
    ok: bool = False
    status: int | None = None
    html: str = ""
    error: str = ""
    fetched_at: datetime | None = None


class PageFetcher:
    """httpx client with UA, timeout, polite delay and robots.txt checks.

    Non-http(s) URLs are read as local fixture files (offline tests/notebooks).

    Example:
        >>> doc = PageFetcher().get("missing/local/page.html")
        >>> doc.ok, doc.error.startswith("local file not found")
        (False, True)
    """

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            timeout=self.settings.fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.settings.user_agent},
            transport=transport,
        )
        self.limiter = RateLimiter(self.settings.fetch_delay_seconds)
        self.robots_cache = DiskCache(self.settings.cache_dir / "robots")

    def get(self, url: str, check_robots: bool = True) -> PageDoc:
        """Fetch `url`; on any failure return a PageDoc with `error` set."""
        if not url.startswith(("http://", "https://")):
            return self._read_local(url)
        if check_robots and self.settings.respect_robots and not self._robots_ok(url):
            return PageDoc(url=url, error="blocked by robots.txt")
        self.limiter.wait()
        try:
            response = self.client.get(url)
            body = response.text
        except Exception as exc:  # network, redirect or decoding failure
            logger.warning("fetch failed for %s: %s", url, exc)
            return PageDoc(url=url, error=str(exc))
        ok = response.status_code == 200
        return PageDoc(
            url=str(response.url),
            ok=ok,
            status=response.status_code,
            html=body if ok else "",
            error="" if ok else f"HTTP {response.status_code}",
            fetched_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------ #
    def _read_local(self, url: str) -> PageDoc:
        path = Path(url)
        if not path.exists():
            return PageDoc(url=url, error=f"local file not found: {url}")
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return PageDoc(url=url, error=f"cannot read {path}: {exc}")
        return PageDoc(url=url, ok=True, html=html, fetched_at=datetime.now(timezone.utc))

    def _robots_ok(self, url: str) -> bool:
        origin = origin_of(url)
        key = self.robots_cache.key("robots", "v1", origin)
        cached = self.robots_cache.get(key)
        if cached is not None and time.time() - float(cached.get("checked", 0)) < _ROBOTS_TTL:
            text = cached.get("text")
        else:
            text = self._fetch_robots(origin)
            self.robots_cache.put(key, {"text": text, "checked": time.time()})
        return robots_allows(url, text, self.settings.user_agent)

    def _fetch_robots(self, origin: str) -> str | None:
        """robots.txt text; None when unreachable (treated as "allow")."""
        self.limiter.wait()
        try:
            response = self.client.get(f"{origin}/robots.txt")
        except Exception as exc:
            logger.info("robots.txt unreachable at %s: %s", origin, exc)
            return None
        if response.status_code != 200:
            return ""
        try:
            return response.text
        except Exception:
            return None
