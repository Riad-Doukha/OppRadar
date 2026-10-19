"""Fetch raw opportunity records from the configured sources.

Three adapters, all returning the same loose shape:

    {"source": "rss:...", "url": ..., "title": ..., "description": ...,
     "published": ..., "raw": {...}}

Failures are per-source: one dead feed logs a warning and moves on.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
import yaml

from oppradar_ai.errors import FetchError

logger = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).with_name("sources.yaml")


def load_sources(path: Path | str = SOURCES_FILE) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return list(data.get("sources", []))


def _http_get(url: str, *, timeout: float = 20.0, user_agent: str) -> httpx.Response:
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise FetchError(f"{url}: {exc}") from exc


# --------------------------------------------------------------------------- #
# RSS / JSON-list adapter (Remotive & friends serve JSON at an RSS-ish URL)
# --------------------------------------------------------------------------- #
def _fetch_rss_or_json(source: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    response = _http_get(
        source["url"],
        timeout=float(defaults.get("timeout_seconds", 20)),
        user_agent=str(defaults.get("user_agent", "OppRadarBot/0.1")),
    )
    content_type = response.headers.get("content-type", "")

    # JSON feed (e.g. Remotive / RemoteOK style APIs)
    if "json" in content_type or source["url"].endswith(("api", "jobs")):
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict):
            data = data.get("jobs") or data.get("data") or data.get("results") or []
        if isinstance(data, list):
            return [_normalise_json_item(source["name"], item) for item in data if isinstance(item, dict)]

    # Real RSS/Atom feed
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise FetchError(f"{source['url']}: not valid RSS/JSON ({exc})") from exc

    records: list[dict[str, Any]] = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "") for child in item}
        link = fields.get("link", "")
        if not link and item.findall("{*}link"):
            link = item.findall("{*}link")[0].get("href", "")
        records.append(
            {
                "source": source["name"],
                "url": link.strip(),
                "title": (fields.get("title") or "").strip(),
                "description": (fields.get("description") or fields.get("summary") or "").strip(),
                "published": (fields.get("pubDate") or fields.get("published") or "").strip(),
                "raw": fields,
            }
        )
    return records


def _normalise_json_item(source_name: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": source_name,
        "url": str(item.get("url") or item.get("link") or ""),
        "title": str(item.get("title") or item.get("name") or ""),
        "description": str(item.get("description") or item.get("summary") or ""),
        "published": str(item.get("publication_date") or item.get("published") or ""),
        "raw": item,
    }


# --------------------------------------------------------------------------- #
# HTML list-page adapter (CSS selectors from sources.yaml)
# --------------------------------------------------------------------------- #
def _fetch_html(source: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover
        raise FetchError("beautifulsoup4 is required for html sources: pip install beautifulsoup4") from exc

    response = _http_get(
        source["url"],
        timeout=float(defaults.get("timeout_seconds", 20)),
        user_agent=str(defaults.get("user_agent", "OppRadarBot/0.1")),
    )
    selector = source.get("selector", {})
    soup = BeautifulSoup(response.text, "html.parser")
    records: list[dict[str, Any]] = []
    for node in soup.select(selector.get("item", "article")):
        title_node = node.select_one(selector.get("title", "h2"))
        link_node = node.select_one(selector.get("link", "a"))
        desc_node = node.select_one(selector.get("description", "p"))
        href = ""
        if link_node is not None:
            href = link_node.get("href", "")
        records.append(
            {
                "source": source["name"],
                "url": str(href),
                "title": title_node.get_text(strip=True) if title_node else "",
                "description": desc_node.get_text(strip=True) if desc_node else "",
                "published": "",
                "raw": node.get_text(" ", strip=True),
            }
        )
    return records


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def fetch_source(source: dict[str, Any], defaults: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    defaults = defaults or {}
    kind = source.get("kind", "rss")
    if kind == "rss":
        return _fetch_rss_or_json(source, defaults)
    if kind == "api":
        return _fetch_rss_or_json(source, defaults)
    if kind == "html":
        return _fetch_html(source, defaults)
    raise FetchError(f"unknown source kind: {kind!r} ({source.get('name')})")


def fetch_all(sources: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch every enabled source (or only the named ones). Continues on error."""
    config = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8")) or {}
    defaults = config.get("defaults", {})
    all_sources = load_sources()

    selected = [
        s
        for s in all_sources
        if s.get("enabled", True) and (sources is None or s["name"] in sources)
    ]

    records: list[dict[str, Any]] = []
    last_hit: dict[str, float] = {}  # per-host rate limiting
    for source in selected:
        host = httpx.URL(source["url"]).host or ""
        wait = float(defaults.get("rate_limit_seconds", 0)) - (time.time() - last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            found = fetch_source(source, defaults)
            logger.info("fetched %d records from %s", len(found), source["name"])
            records.extend(found)
        except FetchError as exc:
            logger.warning("source failed, skipping: %s", exc)
        last_hit[host] = time.time()
    return records
