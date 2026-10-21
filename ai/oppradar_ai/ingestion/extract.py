# Page/feed text -> Opportunity: rules before the LLM, a shared budget
# around it, ISO deadlines that are NEVER invented (rolling/missing ->
# None), and per-field confidence that marks weak fields "to verify".
# Called by: ingestion/pipeline.py, api.py (Phase 7), notebooks 03/04.

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.llm import LLM, get_llm
from oppradar_ai.schemas import (
    FieldConfidence,
    Opportunity,
    OpportunityExtraction,
    OpportunityType,
)

logger = logging.getLogger(__name__)

# Rolling/no-fixed-deadline phrasing (EN + FR): treated as null per spec.
_ONGOING_RE = re.compile(
    r"\b(present|current|ongoing|rolling|continuous|en\s+cours|"
    r"open[\s-]+until[\s-]+filled|no\s+deadline)\b",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "jan": 1, "janvier": 1,
    "february": 2, "feb": 2, "fevrier": 2, "février": 2,
    "march": 3, "mar": 3, "mars": 3,
    "april": 4, "apr": 4, "avril": 4,
    "may": 5, "mai": 5,
    "june": 6, "jun": 6, "juin": 6,
    "july": 7, "jul": 7, "juillet": 7,
    "august": 8, "aug": 8, "aout": 8, "août": 8,
    "september": 9, "sep": 9, "sept": 9, "septembre": 9,
    "october": 10, "oct": 10, "octobre": 10,
    "november": 11, "nov": 11, "novembre": 11,
    "december": 12, "dec": 12, "decembre": 12, "décembre": 12,
}

# Ordered: ISO first, then word-based forms, then all-numeric d/m/y.
_ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_DAY_MONTH_RE = re.compile(r"(?<!\d)(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\.?,?\s+(\d{4})(?!\d)")
_MONTH_DAY_RE = re.compile(r"([A-Za-zÀ-ÿ]+)\s+(\d{1,2}),?\s+(\d{4})(?!\d)")
_DAY_FIRST_RE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")

_OUTPUT_FIELDS = (
    "title", "organizer", "type", "location", "deadline",
    "eligibility", "benefits", "summary", "url",
)


def parse_deadline(raw: str) -> date | None:
    """Normalize a deadline to an ISO date; None when absent/rolling/unknown.

    Never invents: a month without a day, an impossible date or an
    unparseable claim all return None. Numeric d/m/y prefers the day
    first (European/Algerian convention).

    Example:
        >>> parse_deadline("15 March 2027")
        datetime.date(2027, 3, 15)
        >>> parse_deadline("ongoing"), parse_deadline("March 2027")
        (None, None)
    """
    text = (raw or "").strip()
    if not text or _ONGOING_RE.search(text):
        return None
    return _to_date(text)


def find_deadline(text: str) -> str:
    """First well-formed full-date phrase in `text` ("" when none), rules only.

    Example:
        >>> find_deadline("Applications close 30 October 2026. Good luck!")
        '30 October 2026'
    """
    for pattern in (_ISO_RE, _DAY_MONTH_RE, _MONTH_DAY_RE, _DAY_FIRST_RE):
        match = pattern.search(text or "")
        if match and parse_deadline(match.group(0)):
            return match.group(0).strip()
    return ""


def opportunity_id(title: str, url: str = "") -> str:
    """Deterministic id from title + URL (stable across runs, used for dedupe)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "opportunity"
    digest = hashlib.sha1(f"{url}|{title}".encode()).hexdigest()[:8]
    return f"{slug}-{digest}"


def fields_filled(opp: Opportunity) -> int:
    """How many output fields actually carry a value (report metric)."""
    checks = [
        bool(opp.title), bool(opp.organizer), opp.type is not OpportunityType.OTHER,
        bool(opp.mode), bool(opp.location), bool(opp.country),
        opp.deadline is not None, bool(opp.funding),
        bool(opp.eligibility), bool(opp.benefits), bool(opp.summary), bool(opp.url),
    ]
    return sum(1 for check in checks if check)


# --------------------------------------------------------------------------- #
# Deadline internals
# --------------------------------------------------------------------------- #
def _to_date(text: str) -> date | None:
    if match := _ISO_RE.search(text):
        return _valid(int(match[1]), int(match[2]), int(match[3]))
    if match := _DAY_MONTH_RE.search(text):
        month = _MONTHS.get(match[2].lower())
        if month:
            return _valid(int(match[3]), month, int(match[1]))
    if match := _MONTH_DAY_RE.search(text):
        month = _MONTHS.get(match[1].lower())
        if month:
            return _valid(int(match[3]), month, int(match[2]))
    if match := _DAY_FIRST_RE.search(text):
        first, second, year = int(match[1]), int(match[2]), int(match[3])
        day, month = (second, first) if second > 12 else (first, second)
        return _valid(year, month, day)
    return None


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:  # e.g. 2027-02-30 — never emit an impossible date
        return None


def _deadline(raw: str, text: str, conf: dict[str, float]) -> tuple[date | None, float]:
    """(ISO date or None, confidence). A claim that cannot be parsed -> None."""
    parsed = parse_deadline(raw)
    if parsed is not None:
        return parsed, conf.get("deadline", 0.8)
    if raw.strip():  # something was claimed but unparseable: flag, don't guess
        return None, min(conf.get("deadline", 0.5), 0.2)
    if from_text := parse_deadline(find_deadline(text)):  # rules found it
        return from_text, 0.75
    return None, 0.4  # source states no deadline -> empty and "to verify"


# --------------------------------------------------------------------------- #
# Extraction -> Opportunity
# --------------------------------------------------------------------------- #
def to_opportunity(
    extraction: OpportunityExtraction,
    *,
    url: str = "",
    source_name: str = "unknown",
    source_checked: datetime | None = None,
    text: str = "",
    title_hint: str = "",
    type_hint: OpportunityType = OpportunityType.OTHER,
    language: str = "en",
    country: str = "",
    settings: Settings | None = None,
) -> Opportunity:
    """Extraction -> validated Opportunity with ISO deadline + confidences.

    Deadline policy: only dates actually present in the source survive;
    unparseable or rolling deadlines become None and stay "to verify".

    Raises:
        ValueError: when no title (LLM or hint) and no organizer (LLM or
            URL host) are available — callers degrade to `_fallback`.
    """
    settings = settings or get_settings()
    conf = {fc.field: fc.confidence for fc in extraction.field_confidences}
    title = extraction.title.strip() or title_hint.strip()
    if not title:
        raise ValueError("no title available")
    organizer = extraction.organizer.strip() or _host_of(url)
    if not organizer:
        raise ValueError("no organizer available")
    deadline, deadline_conf = _deadline(extraction.deadline, text, conf)
    country = country or extraction.country
    marks = _marks(
        extraction, conf, deadline, deadline_conf, url,
        settings.confidence_threshold,
    )
    return Opportunity(
        id=opportunity_id(title, url),
        title=title,
        organizer=organizer,
        type=_type_of(extraction.type, type_hint),
        mode=extraction.mode,
        location=extraction.location.strip(),
        country=country.strip(),
        language=language,
        deadline=deadline,
        funding=extraction.funding,
        eligibility=[e.strip() for e in extraction.eligibility if e.strip()],
        benefits=[b.strip() for b in extraction.benefits if b.strip()],
        summary=extraction.summary.strip(),
        url=url,
        source=source_name,
        source_checked=source_checked or datetime.now(timezone.utc),
        added_via="pipeline",
        field_confidences=marks,
    )


def _marks(
    extraction: OpportunityExtraction,
    conf: dict[str, float],
    deadline: date | None,
    deadline_conf: float,
    url: str,
    threshold: float,
) -> list[FieldConfidence]:
    """One FieldConfidence per output field; weak or missing -> needs_review."""
    values: dict[str, float] = {
        "title": conf.get("title", 0.7),
        "organizer": conf.get("organizer", 0.7 if extraction.organizer.strip() else 0.4),
        "type": conf.get("type", 0.7),
        "location": conf.get("location", 0.7 if extraction.location else 0.3),
        "deadline": deadline_conf,
        "eligibility": conf.get("eligibility", 0.7 if extraction.eligibility else 0.3),
        "benefits": conf.get("benefits", 0.7 if extraction.benefits else 0.3),
        "summary": conf.get("summary", 0.7 if extraction.summary else 0.3),
        "url": 0.95 if url else 0.0,
    }
    marks = []
    for name, value in values.items():
        value = round(min(max(value, 0.0), 1.0), 2)
        needs = value < threshold or (name == "deadline" and deadline is None)
        marks.append(FieldConfidence(field=name, confidence=value, needs_review=needs))
    return marks


def _type_of(extracted: OpportunityType, hint: OpportunityType) -> OpportunityType:
    if extracted is OpportunityType.OTHER and hint is not OpportunityType.OTHER:
        return hint
    return extracted


def _host_of(url: str) -> str:
    return urlsplit(url).netloc if url else ""


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:120]
    return ""


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def extract_from_text(
    text: str,
    *,
    url: str = "",
    source_name: str = "unknown",
    title_hint: str = "",
    type_hint: OpportunityType = OpportunityType.OTHER,
    language: str = "en",
    country: str = "",
    budget: RunBudget | None = None,
    settings: Settings | None = None,
    checked_at: datetime | None = None,
) -> Opportunity | None:
    """Extract one opportunity from `text` (budgeted LLM, rules-backed).

    Disk-cache hits are free; only real LLM calls consume `budget`. When
    the budget is spent or the provider fails, this degrades to a
    rules-only Opportunity whose every field is marked "to verify".

    Pass a shared `RunBudget` to cap a whole batch; without one each
    call gets its own fresh quota. Returns None only when no usable
    title exists at all.

    Example:
        >>> opp = extract_from_text("Deadline 15 March 2027", source_name="t")
        >>> opp is None or opp.deadline.year == 2027
        True
    """
    settings = settings or get_settings()
    budget = budget or RunBudget(settings)
    checked = checked_at or datetime.now(timezone.utc)
    system = (settings.prompts_dir / "extract_opportunity.md").read_text(encoding="utf-8")
    extraction = _extract(get_llm(), text, system, budget)
    if extraction is not None:
        try:
            return to_opportunity(
                extraction,
                url=url,
                source_name=source_name,
                source_checked=checked,
                text=text,
                title_hint=title_hint,
                type_hint=type_hint,
                language=language,
                country=country,
                settings=settings,
            )
        except ValueError as exc:
            logger.warning("extraction unusable for %s: %s", url or source_name, exc)
    return _fallback(
        text, url, source_name, title_hint, type_hint, language, country, checked
    )


def _extract(
    llm: LLM,
    text: str,
    system: str,
    budget: RunBudget,
) -> OpportunityExtraction | None:
    """One budgeted, cached LLM call; None on skip/failure (never raises)."""
    if llm.is_cached(text, OpportunityExtraction, system):
        budget.extractions.cached += 1
    elif not budget.allow_extraction():
        budget.extractions.skipped += 1
        logger.warning(
            "extraction budget (%d) spent; using rules only for the next page",
            budget.extractions.limit,
        )
        return None
    try:
        return llm.structured(text, OpportunityExtraction, system=system)
    except Exception as exc:  # provider errors must never kill a run
        logger.warning("LLM extraction failed (%s); using rules only", exc)
        return None


def _fallback(
    text: str,
    url: str,
    source_name: str,
    title_hint: str,
    type_hint: OpportunityType,
    language: str,
    country: str,
    checked: datetime,
) -> Opportunity | None:
    """Rules-only opportunity (no LLM): every field marked "to verify"."""
    title = title_hint.strip() or _first_line(text)
    if not title:
        logger.warning("no usable title for %s", url or source_name)
        return None
    deadline = parse_deadline(find_deadline(text))
    marks = [
        FieldConfidence(field=name, confidence=0.3, needs_review=True)
        for name in _OUTPUT_FIELDS
    ]
    return Opportunity(
        id=opportunity_id(title, url),
        title=title,
        organizer=_host_of(url) or source_name,
        type=type_hint,
        deadline=deadline,
        url=url,
        source=source_name,
        source_checked=checked,
        language=language,
        country=country,
        added_via="pipeline",
        field_confidences=marks,
    )
