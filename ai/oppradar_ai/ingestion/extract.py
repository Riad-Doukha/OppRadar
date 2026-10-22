# Page/feed text -> Opportunity: rules before the LLM, a shared budget
# around it, ISO deadlines that are NEVER invented (rolling/missing ->
# None), rule-first "Deadline:" lines that beat the model, the
# is_opportunity gate (listicles/news -> rejected) and per-field
# confidence that marks weak fields "to verify".
# Called by: ingestion/pipeline.py, api.py (Phase 7), notebooks 03/04.

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from pydantic import BaseModel

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
    r"\b(present|current|ongoing|rolling|continuous|varies|unspecified|tbd|"
    r"to\s+be\s+announced|open[\s-]+until[\s-]+filled|no\s+deadline)\b|"
    r"en\s+cours|à\s+définir|a\s+definir|à\s+confirmer|a\s+confirmer",
    re.IGNORECASE,
)

# Explicit "Deadline: <phrase>" line (EN + FR): this RULE always beats the
# model's value — sources state deadlines; models may hallucinate them.
_DEADLINE_LINE_RE = re.compile(
    r"(?:\bdeadline\b|\bdate\s+limite\b|\bdate\s+butoir\b)"
    r"\s*(?:de\s+candidature\s*)?(?:is|are|:|\-|–|—)\s*"
    r"([^\n.;|]{1,60})",
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


def deadline_line(text: str) -> str:
    """Raw phrase after an explicit "Deadline:"/"Date limite:" prefix ("" when none).

    Returns the phrase exactly as written ("30 November 2026", "On Rolling
    Basis", ...); the caller parses it with `parse_deadline`.

    Example:
        >>> deadline_line("Applications open. Deadline: 30 November 2026.")
        '30 November 2026'
        >>> deadline_line("Date limite de candidature : 15 mars 2027")
        '15 mars 2027'
        >>> deadline_line("no deadline line at all")
        ''
    """
    match = _DEADLINE_LINE_RE.search(text or "")
    return match.group(1).strip() if match else ""


def truncate_text(text: str, limit: int) -> str:
    """Cut text to `limit` chars with an explicit marker (LLM input control).

    Example:
        >>> truncate_text("x" * 20, 10)
        'xxxxxxxxxx\\n[...truncated...]'
    """
    text = text or ""
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "\n[...truncated...]"


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


def _deadline(
    raw: str, text: str, conf: dict[str, float]
) -> tuple[date | None, float, str, str]:
    """(ISO date or None, confidence, source, review note). Rule-first policy.

    A parseable "Deadline: <date>" line in the source ALWAYS beats the
    model's value; a "Deadline: Rolling Basis" line keeps it null even if
    the model claims a date. The note documents any disagreement.
    """
    llm_date = parse_deadline(raw)
    rule_raw = deadline_line(text)
    rule_date = parse_deadline(rule_raw)
    if rule_raw and rule_date:  # explicit source deadline wins
        if llm_date and llm_date != rule_date:
            return rule_date, 0.5, "rule", (
                f"deadline mismatch: rule {rule_date} vs model {llm_date} (kept rule)"
            )
        return rule_date, 0.9, "rule", ""
    if rule_raw:  # "Deadline: Rolling Basis" etc. -> null, even against the model
        if llm_date:
            return None, 0.3, "none", (
                f"deadline mismatch: source says {rule_raw!r}, "
                f"model claimed {llm_date} (kept null)"
            )
        return None, 0.5, "none", ""
    if llm_date:  # no explicit line: trust the model's parseable value
        return llm_date, conf.get("deadline", 0.8), "llm", ""
    if raw.strip():  # something was claimed but unparseable: flag, don't guess
        return None, min(conf.get("deadline", 0.5), 0.2), "none", ""
    if from_text := parse_deadline(find_deadline(text)):  # loose rule backfill
        return from_text, 0.75, "rule", ""
    return None, 0.4, "none", ""  # source states no deadline -> empty + "to verify"


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
    list_page: bool = False,
) -> Opportunity:
    """Extraction -> validated Opportunity with ISO deadline + confidences.

    Deadline policy: a parseable "Deadline:" line in the source wins over
    the model; unparseable or rolling deadlines become None and stay
    "to verify". `list_page=True` (an index page) forces every field to
    low confidence plus a "list page - needs detail" review note.

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
    deadline, deadline_conf, deadline_source, note = _deadline(
        extraction.deadline, text, conf
    )
    country = country or extraction.country
    marks = _marks(
        extraction, conf, deadline, deadline_conf, url,
        settings.confidence_threshold, deadline_review=bool(note), list_page=list_page,
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
        deadline_source=deadline_source,
        funding=extraction.funding,
        eligibility=[e.strip() for e in extraction.eligibility if e.strip()],
        benefits=[b.strip() for b in extraction.benefits if b.strip()],
        summary=extraction.summary.strip(),
        url=url,
        source=source_name,
        source_checked=source_checked or datetime.now(timezone.utc),
        added_via="pipeline",
        field_confidences=marks,
        review_notes=_review_notes(note, list_page),
    )


def _marks(
    extraction: OpportunityExtraction,
    conf: dict[str, float],
    deadline: date | None,
    deadline_conf: float,
    url: str,
    threshold: float,
    *,
    deadline_review: bool = False,
    list_page: bool = False,
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
        if deadline_review and name == "deadline":  # rule/model disagreed
            value, needs = min(value, 0.5), True
        if list_page:  # an index page carries no reliable field values
            value, needs = min(value, 0.4), True
        marks.append(FieldConfidence(field=name, confidence=value, needs_review=needs))
    return marks


def _review_notes(deadline_note: str, list_page: bool) -> list[str]:
    notes = [deadline_note] if deadline_note else []
    if list_page:
        notes.append("list page - needs detail")
    return notes


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
class RawExtraction(BaseModel):
    """Outcome of one budgeted extraction: an accepted record OR a rejection.

    `rejected_reason` is set when the model says the text is not a real
    opportunity (listicle, career advice, news) — such items never become
    Opportunity records. `extraction` always holds the raw model answer.
    """

    opportunity: Opportunity | None = None
    rejected_reason: str | None = None
    extraction: OpportunityExtraction | None = None
    url: str = ""
    llm_provider: str = ""  # "" = no LLM answered (budget skip/failure)
    llm_model: str = ""


def extract_record(
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
    list_page: bool = False,
) -> RawExtraction:
    """Extract one record from `text` — accepted Opportunity or rejection reason.

    Same budget/cache/fallback behaviour as `extract_from_text`, plus the
    `is_opportunity` gate (listicles/news/advice are rejected, kept in the
    report only) and provider/model provenance of the answering call.

    Example:
        >>> out = extract_record("Top 10 scholarships of 2026!", source_name="t")
        >>> bool(out.rejected_reason), out.extraction is not None
        (True, True)
    """
    settings = settings or get_settings()
    budget = budget or RunBudget(settings)
    checked = checked_at or datetime.now(timezone.utc)
    system = (settings.prompts_dir / "extract_opportunity.md").read_text(encoding="utf-8")
    llm = get_llm()
    extraction = _extract(llm, text, system, budget)
    provider, model = _llm_identity(llm, text, system)
    if extraction is not None and not extraction.is_opportunity:
        reason = extraction.not_opportunity_reason.strip() or "not a single opportunity"
        logger.info("rejected %s: %s", url or source_name, reason)
        return RawExtraction(
            rejected_reason=reason, extraction=extraction, url=url,
            llm_provider=provider, llm_model=model,
        )
    try:
        opp = (
            to_opportunity(
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
                list_page=list_page,
            )
            if extraction is not None
            else _fallback(
                text, url, source_name, title_hint, type_hint, language, country, checked
            )
        )
    except ValueError as exc:
        logger.warning("extraction unusable for %s: %s", url or source_name, exc)
        opp = None
    return RawExtraction(
        opportunity=opp, extraction=extraction, url=url,
        llm_provider=provider, llm_model=model,
    )


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
    list_page: bool = False,
) -> Opportunity | None:
    """Extract one opportunity from `text` (budgeted LLM, rules-backed).

    Thin wrapper over `extract_record` kept for notebooks: rejected items
    (is_opportunity=false) return None here. Disk-cache hits are free;
    when the budget is spent or the provider fails this degrades to a
    rules-only Opportunity whose every field is marked "to verify".
    Returns None only when no usable title exists at all.

    Example:
        >>> opp = extract_from_text("Deadline 15 March 2027", source_name="t")
        >>> opp is None or opp.deadline.year == 2027
        True
    """
    return extract_record(
        text,
        url=url,
        source_name=source_name,
        title_hint=title_hint,
        type_hint=type_hint,
        language=language,
        country=country,
        budget=budget,
        settings=settings,
        checked_at=checked_at,
        list_page=list_page,
    ).opportunity


def _llm_identity(llm: LLM, text: str, system: str) -> tuple[str, str]:
    """Provider/model recorded with the (possibly cached) extraction call."""
    meta_fn = getattr(llm, "cached_meta", None)
    meta = meta_fn(text, OpportunityExtraction, system=system) if callable(meta_fn) else None
    if not meta:
        return "", ""  # no record: budget skipped the call or the provider failed
    return str(meta.get("provider", "")), str(meta.get("model", ""))


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
        deadline_source="rule" if deadline is not None else "none",
        url=url,
        source=source_name,
        source_checked=checked,
        language=language,
        country=country,
        added_via="pipeline",
        field_confidences=marks,
        review_notes=["llm skipped or failed - rules only"],
    )
