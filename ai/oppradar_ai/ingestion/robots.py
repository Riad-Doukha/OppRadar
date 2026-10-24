# robots.txt logic: parse the rules per origin and answer can-fetch
# questions. Missing/unreachable robots.txt means "allow" (standard
# practice); fetching + caching happens in ingestion/fetch.py.

from __future__ import annotations

import logging
import urllib.parse
import urllib.robotparser

logger = logging.getLogger(__name__)


def origin_of(url: str) -> str:
    """Scheme + host of `url` (the scope robots.txt applies to).

    Example:
        >>> origin_of("https://example.org/a/b?x=1")
        'https://example.org'
    """
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def parse_robots(text: str) -> urllib.robotparser.RobotFileParser:
    """Parse robots.txt content into a queryable parser.

    Example:
        >>> parse_robots("User-agent: *\\nDisallow: /").can_fetch("bot", "/x")
        False
    """
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())  # parse() also marks it as "checked"
    return parser


def robots_allows(url: str, text: str | None, user_agent: str) -> bool:
    """May `user_agent` fetch `url` given robots.txt `text`?

    `text=None` (unreachable) or `text=""` (no rules) both mean "allow".

    Example:
        >>> robots_allows("https://e.org/x", "User-agent: *\\nDisallow: /", "bot")
        False
        >>> robots_allows("https://e.org/x", None, "bot")
        True
    """
    if not text:
        return True
    allowed = parse_robots(text).can_fetch(user_agent, url)
    if not allowed:
        logger.info("robots.txt disallows %s for %s", url, user_agent)
    return allowed
