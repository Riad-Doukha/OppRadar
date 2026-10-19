"""De-duplicate opportunities.

Order matters: cheap, deterministic URL canonicalisation first; fuzzy title
matching only for records that survived it.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rapidfuzz import fuzz

from oppradar_ai.schemas import Opportunity

# Two records at or above this token-set ratio are the same opportunity.
SIMILARITY_THRESHOLD = 92

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "source")


def canonical_url(url: str) -> str:
    """Lowercase scheme+host, drop tracking params, strip trailing slashes."""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/")
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")  # drop fragments
    )


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation — for comparison only."""
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in title)
    return " ".join(cleaned.split())


def similarity(a: Opportunity, b: Opportunity) -> int:
    """Fuzzy similarity (0-100) of title + organization."""
    left = f"{normalize_title(a.title)} {normalize_title(a.organization)}"
    right = f"{normalize_title(b.title)} {normalize_title(b.organization)}"
    return int(fuzz.token_set_ratio(left, right))


def _merge(base: Opportunity, other: Opportunity) -> Opportunity:
    """Merge a duplicate into `base`: richest description, latest deadline."""
    data = base.model_dump()
    other_data = other.model_dump()
    if len(other_data["description"]) > len(data["description"]):
        data["description"] = other_data["description"]
    if other_data["deadline"] and (
        data["deadline"] is None or other_data["deadline"] > data["deadline"]
    ):
        data["deadline"] = other_data["deadline"]
    data["tags"] = sorted(set(data["tags"]) | set(other_data["tags"]))[:8]
    if other.scam and (base.scam is None or other.scam.score > base.scam.score):
        data["scam"] = other.scam
    return Opportunity.model_validate(data)


def dedupe(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Remove exact (URL) and fuzzy (title+org) duplicates, merging their fields."""
    by_url: dict[str, Opportunity] = {}
    for opp in opportunities:
        key = canonical_url(opp.source_url)
        if key in by_url:
            by_url[key] = _merge(by_url[key], opp)
        else:
            by_url[key] = opp

    unique: list[Opportunity] = []
    normalized_titles: list[str] = []
    for opp in by_url.values():
        title = normalize_title(f"{opp.title} {opp.organization}")
        match_index = next(
            (
                i
                for i, seen in enumerate(normalized_titles)
                if fuzz.token_set_ratio(title, seen) >= SIMILARITY_THRESHOLD
            ),
            None,
        )
        if match_index is None:
            normalized_titles.append(title)
            unique.append(opp)
        else:
            unique[match_index] = _merge(unique[match_index], opp)
    return unique
