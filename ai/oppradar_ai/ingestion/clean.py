# HTML -> readable text via trafilatura: page title, main body text and
# outbound links. Best effort: unreadable/garbage HTML yields an empty
# result, never a crash. Called by: ingestion/pipeline.py, notebook 04.

from __future__ import annotations

import logging
import re

import trafilatura
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', re.IGNORECASE
)
_CANONICAL_HREF_FIRST_RE = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.IGNORECASE
)
_OG_URL_RE = re.compile(
    r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE
)


class CleanedPage(BaseModel):
    """Readable content of one HTML document."""

    url: str = ""
    canonical: str = ""  # permalink declared by the page (else "")
    title: str = ""
    text: str = ""
    links: list[str] = Field(default_factory=list)


def clean_html(html: str, url: str = "") -> CleanedPage:
    """Extract canonical URL, title, main text and links from raw HTML.

    Example:
        >>> page = clean_html("<title>T</title><article><p>Body</p></article>")
        >>> page.title, page.text
        ('T', 'Body')
    """
    text = ""
    try:
        text = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=False
        )
    except Exception as exc:  # malformed markup must not crash a run
        logger.warning("cleaning failed for %s: %s", url or "<html>", exc)
    return CleanedPage(
        url=url,
        canonical=_canonical(html),
        title=_title(html),
        text=(text or "").strip(),
        links=_links(html),
    )


def _canonical(html: str) -> str:
    for pattern in (_CANONICAL_RE, _OG_URL_RE, _CANONICAL_HREF_FIRST_RE):
        match = pattern.search(html)
        if match:
            return match.group(1).strip()
    return ""


def _title(html: str) -> str:
    try:
        meta = trafilatura.extract_metadata(html)
        if meta is not None and getattr(meta, "title", None):
            return str(meta.title).strip()
    except Exception:
        pass
    match = _TITLE_RE.search(html)
    return match.group(1).strip() if match else ""


def _links(html: str) -> list[str]:
    try:
        from lxml import html as lxml_html

        hrefs = lxml_html.fromstring(html).xpath("//a/@href")
    except Exception:
        return []
    return list(dict.fromkeys(h for h in (str(h).strip() for h in hrefs) if h.startswith("http")))
