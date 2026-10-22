# Rules-first extraction: cheap regexes find emails/phones/links before the LLM
# fills the structured schema (CVExtraction, ...). Prompt text lives in prompts/.

from __future__ import annotations

import logging
import re

from oppradar_ai.config import get_settings
from oppradar_ai.llm import get_llm
from oppradar_ai.schemas import CertificateExtraction, CVExtraction, PortfolioExtraction

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://[^\s<>()\"']+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_YEAR_RANGE_RE = re.compile(r"(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}")


def find_emails(text: str) -> list[str]:
    """Every e-mail address in `text`, deduplicated, in order.

    Example:
        >>> find_emails("write a@b.com or a@b.com")
        ['a@b.com']
    """
    return list(dict.fromkeys(m.group(0) for m in _EMAIL_RE.finditer(text)))


def find_urls(text: str) -> list[str]:
    """Every http(s) URL in `text`, deduplicated, in order."""
    return list(dict.fromkeys(m.group(0).rstrip(".,;") for m in _URL_RE.finditer(text)))


def find_phones(text: str) -> list[str]:
    """Every plausible phone number in `text`, deduplicated, in order.

    Four-digit year ranges such as "2021 - 2024" are rejected: in CVs,
    digits around a hyphen are dates, never phone numbers.

    Example:
        >>> find_phones("call +213 555 000 111 or start 2021 - 2024")
        ['+213 555 000 111']
    """
    cands = (m.group(0).strip() for m in _PHONE_RE.finditer(text))
    return list(dict.fromkeys(c for c in cands if not _YEAR_RANGE_RE.fullmatch(c)))


def _load_prompt(name: str) -> str:
    path = get_settings().prompts_dir / name
    return path.read_text(encoding="utf-8")


def extract_cv(text: str, source_file: str = "") -> CVExtraction:
    """CV text -> structured CVExtraction (rules first, then the LLM).

    Example:
        >>> cv = extract_cv("Amine ... a@b.com", "cv.pdf")
        >>> isinstance(cv, CVExtraction)
        True
    """
    cv = get_llm().structured(text, CVExtraction, system=_load_prompt("extract_cv.md"))
    cv.source_file = source_file  # set first so backfill logs can name the file
    _backfill(cv, text)
    logger.info("extracted CV %r (%d skills, source=%s)", cv.full_name, len(cv.skills), source_file)
    return cv


def extract_certificate(text: str, source_file: str = "") -> CertificateExtraction:
    """Certificate text -> structured CertificateExtraction."""
    ext = get_llm().structured(
        text, CertificateExtraction, system=_load_prompt("extract_certificate.md")
    )
    if not ext.credential_url and (urls := find_urls(text)):
        ext.credential_url = urls[0]
    ext.source_file = source_file
    return ext


def extract_portfolio(text: str, source_file: str = "") -> PortfolioExtraction:
    """Portfolio text -> structured PortfolioExtraction."""
    ext = get_llm().structured(
        text, PortfolioExtraction, system=_load_prompt("extract_portfolio.md")
    )
    if not ext.email and (emails := find_emails(text)):
        ext.email = emails[0]
    if not ext.links:
        ext.links = find_urls(text)
    ext.source_file = source_file
    return ext


def _backfill(cv: CVExtraction, text: str) -> None:
    """Fill fields the LLM left empty from the cheap regex rules."""
    filled: list[str] = []
    if not cv.email and (emails := find_emails(text)):
        cv.email = emails[0]
        filled.append("email")
    if not cv.phone and (phones := find_phones(text)):
        cv.phone = phones[0]
        filled.append("phone")
    if not cv.links:
        cv.links = find_urls(text)
        filled.append("links")
    if filled:
        logger.info(
            "regex backfill filled %s for %s",
            ", ".join(filled),
            cv.source_file or "(inline text, no filename given)",
        )
