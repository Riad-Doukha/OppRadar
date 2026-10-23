# The stable AI <-> backend interface: six functions, plain Pydantic in/out,
# no database, no side effects beyond the local disk cache. Every remote step
# is gated by RUN_LIVE_LLM; every expected failure raises ApiError with a
# machine-readable `code`. Called by: the backend (docs/ai-interface.md) and
# the end-to-end tests.

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from oppradar_ai.config import Settings, forced_provider, get_settings
from oppradar_ai.documents.extractors import (
    extract_certificate,
    extract_cv,
    extract_portfolio,
    find_emails,
    find_urls,
)
from oppradar_ai.documents.profile_builder import Extraction, build_profile
from oppradar_ai.documents.reader import read_document
from oppradar_ai.ingestion.clean import clean_html
from oppradar_ai.ingestion.extract import extract_record
from oppradar_ai.ingestion.fetch import PageFetcher
from oppradar_ai.ingestion.pipeline import live_fetch_allowed
from oppradar_ai.ingestion.pipeline import run_ingestion as _run
from oppradar_ai.matching.composer import score_user as _score
from oppradar_ai.matching.notifications import decide_notifications as _decide
from oppradar_ai.private_profile import rules_only_cv
from oppradar_ai.schemas import (
    CertificateExtraction,
    ChatAnswer,
    ChatTurn,
    IngestionReport,
    MatchResult,
    Notification,
    NotificationPrefs,
    Opportunity,
    PortfolioExtraction,
    Profile,
    Source,
)

logger = logging.getLogger(__name__)

# Document kinds parse_documents understands (kinds= overrides the heuristic).
_KINDS = ("cv", "certificate", "portfolio")


class ApiError(Exception):
    """Every expected failure of the public interface (the backend maps `code`).

    Codes: `empty`, `unreadable`, `arguments`, `offline`, `fetch`, `rejected`,
    `pending`, `unusable`, `chat-unavailable`, `api_error`.

    Example:
        >>> ApiError("nothing to parse", code="empty").code
        'empty'
    """

    def __init__(self, message: str, *, code: str = "api_error") -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Documents -> Profile
# --------------------------------------------------------------------------- #
def parse_documents(
    files: list[str | Path],
    *,
    user_id: str = "local-user",
    kinds: list[str] | None = None,
    allow_llm: bool = False,
) -> Profile:
    """Parse the user's documents (CV / certificate / portfolio) into one Profile.

    The default route is rules-only: documents never reach a remote model, so
    the privacy contract holds whatever .env says. `allow_llm=True` runs the
    configured provider over every document — only for backends that collected
    the user's explicit consent. `kinds` labels the files ("cv", "certificate",
    "portfolio"); without it, a coarse text heuristic is used.

    Raises:
        ApiError: no files given (`empty`) or no document produced any text
            (`unreadable`).

    Example:
        >>> profile = parse_documents(["data/samples/cv_amine.pdf"])   # doctest: +SKIP
        >>> profile.source_files
        ['cv_amine.pdf']
    """
    if not files:
        raise ApiError("no documents given", code="empty")
    if kinds is not None and any(kind not in _KINDS for kind in kinds):
        raise ApiError(f"unknown kind (expected one of {_KINDS})", code="arguments")
    extractions, errors = _read_all(files, kinds, allow_llm)
    if not extractions:
        raise ApiError("; ".join(errors) or "no readable documents", code="unreadable")
    return build_profile(extractions, user_id, errors=errors).profile


def detect_kind(text: str) -> str:
    """Coarse document kind when the backend did not label the upload.

    Example:
        >>> detect_kind("Certificate of completion, issued 2024")
        'certificate'
        >>> detect_kind("Amine, data science student, a@b.com")
        'cv'
    """
    head = (text or "")[:4000].casefold()
    if any(word in head for word in ("certificate", "certificat", "diploma", "attestation")):
        return "certificate"
    if "portfolio" in head:
        return "portfolio"
    return "cv"


def _read_all(
    files: list[str | Path], kinds: list[str] | None, allow_llm: bool
) -> tuple[list[Extraction], list[str]]:
    """Read + extract every file; unreadable files become error strings."""
    extractions: list[Extraction] = []
    errors: list[str] = []
    for index, raw in enumerate(files):
        path = Path(raw)
        try:
            text = _read_text(path, allow_llm)
        except Exception as exc:  # one broken file must not kill the rest
            errors.append(f"{path.name}: {exc}")
            logger.warning("cannot read %s: %s", path.name, exc)
            continue
        kind = kinds[index] if kinds and index < len(kinds) else detect_kind(text)
        extractions.append(_extract_kind(kind, text, path.name, allow_llm))
    return extractions, errors


def _read_text(path: Path, allow_llm: bool) -> str:
    """Read one document; the rules-only route forces the fake provider so the
    reader's vision fallback can never send a scan to Gemini."""
    if allow_llm:
        return read_document(path).text
    with forced_provider("fake"):
        return read_document(path).text


def _extract_kind(kind: str, text: str, source_file: str, allow_llm: bool) -> Extraction:
    """One document -> its structured extraction (LLM route or rules-only)."""
    if allow_llm:
        if kind == "certificate":
            return extract_certificate(text, source_file)
        if kind == "portfolio":
            return extract_portfolio(text, source_file)
        return extract_cv(text, source_file)
    if kind == "certificate":
        return CertificateExtraction(
            credential_url=(find_urls(text) or [""])[0], source_file=source_file
        )
    if kind == "portfolio":
        return PortfolioExtraction(
            email=(find_emails(text) or [""])[0], links=find_urls(text), source_file=source_file
        )
    return rules_only_cv(text, source_file)


# --------------------------------------------------------------------------- #
# Web -> Opportunity
# --------------------------------------------------------------------------- #
def run_ingestion(
    sources: list[Source] | None = None, *, settings: Settings | None = None
) -> IngestionReport:
    """Run one ingestion pass over `sources` (default: data/sources.yaml).

    Feed entries are extracted in batches (`extraction_batch_size` entries per
    call); a failing source never kills the run — it becomes a report failure.

    Example:
        >>> run_ingestion(sources=[]).items_new # doctest: +SKIP
        0
    """
    return _run(sources, settings=settings)


def extract_opportunity(
    url: str | None = None,
    text: str | None = None,
    image: str | Path | None = None,
    *,
    source_name: str = "manual",
    settings: Settings | None = None,
) -> Opportunity:
    """Extract ONE opportunity from a URL, pasted text or an image (OCR).

    Exactly one source must be given. `text` may be raw HTML (cleaned first);
    `image` is OCR'd locally; `url` fetches the page live (robots.txt honored)
    and therefore needs the gate: RUN_LIVE_LLM=1 plus a real provider.

    Raises:
        ApiError: nothing/more than one given (`arguments`), a refused live
            fetch (`offline`) or failed download (`fetch`), a rejected text
            (`rejected`), an unanswered extraction (`pending`) or one without a
            usable title/organizer (`unusable`).
    """
    settings = settings or get_settings()
    given = [name for name, value in (("url", url), ("text", text), ("image", image)) if value]
    if len(given) != 1:
        raise ApiError("give exactly one of url=, text= or image=", code="arguments")
    if text is not None:
        body, page_url = _page_text(str(text)), ""
    elif image is not None:
        body, page_url = read_document(Path(image)).text, ""
    else:
        body, page_url = _fetch_page(str(url), settings), str(url)
    outcome = extract_record(
        body, url=page_url, source_name=source_name, settings=settings
    )
    if outcome.pending is not None:
        raise ApiError(f"no LLM answer: {outcome.pending.reason}", code="pending")
    if outcome.rejected_reason is not None:
        raise ApiError(f"not an opportunity: {outcome.rejected_reason}", code="rejected")
    if outcome.opportunity is None:
        raise ApiError("extraction had no usable title/organizer", code="unusable")
    return outcome.opportunity


def _page_text(body: str) -> str:
    """Use the cleaned page text of raw HTML; pass plain text through unchanged."""
    head = body[:2000].casefold()
    if "<html" in head or "<body" in head:
        return clean_html(body).text
    return body


def _fetch_page(url: str, settings: Settings) -> str:
    """Fetch one page live (gate + robots); ApiError when the gate is closed."""
    if not live_fetch_allowed(settings, url):
        raise ApiError(
            "live fetching is off: set RUN_LIVE_LLM=1 with a real provider",
            code="offline",
        )
    doc = PageFetcher(settings).get(url)
    if not doc.ok:
        raise ApiError(f"cannot fetch {url}: {doc.error}", code="fetch")
    return clean_html(doc.html, url).text


# --------------------------------------------------------------------------- #
# Matching + notifications
# --------------------------------------------------------------------------- #
def score_user(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    settings: Settings | None = None,
    today: date | None = None,
) -> list[MatchResult]:
    """Hard filters + a 0-100 score with reasons, best first.

    Example:
        >>> score_user(profile, opportunities)   # doctest: +SKIP
        [MatchResult(score=82.5, ...)]
    """
    return _score(profile, opportunities, settings=settings, today=today)


def decide_notifications(
    matches: list[MatchResult],
    prefs: NotificationPrefs,
    history: list[Notification],
    *,
    now: datetime | None = None,
) -> list[Notification]:
    """Threshold, daily cap, quiet hours and dedupe — one row per match.

    Example:
        >>> decide_notifications(matches, prefs, [], now=now)   # doctest: +SKIP
        [Notification(status='sent', ...)]
    """
    return _decide(matches, prefs, history, now=now)


# --------------------------------------------------------------------------- #
# Chat (module lands with the chat phase)
# --------------------------------------------------------------------------- #
def answer(
    profile: Profile,
    opportunity: Opportunity | None,
    history: list[ChatTurn],
    message: str,
    *,
    settings: Settings | None = None,
) -> ChatAnswer:
    """Grounded answer to one user message (frozen Phase-7 signature).

    The chat module is built on its own branch; until it lands, calling this
    raises ApiError(`chat-unavailable`) instead of pretending to answer.

    Example:
        >>> answer(profile, opportunity, [], "Deadline?")   # doctest: +SKIP
        ChatAnswer(answer='...', in_source=True)
    """
    try:
        from oppradar_ai.chat import answer as chat_answer
    except ImportError as exc:
        raise ApiError(
            "the chat module is not available yet (phase: chat)",
            code="chat-unavailable",
        ) from exc
    try:
        reply = chat_answer(profile, opportunity, history, message, settings=settings)
    except TypeError as exc:  # a signature drift must surface as our error
        raise ApiError(
            f"chat.answer() signature mismatch: {exc}", code="chat-unavailable"
        ) from exc
    return ChatAnswer.model_validate(reply)
