"""The backend's single doorway into the AI package (oppradar_ai).

Routers never import oppradar_ai directly: when an AI phase lands (matching,
ingestion, chat, notifications), it is wired here and nowhere else.

Available today (AI Phase 2): document reading + CV/certificate/portfolio
extraction. Later phases are listed at the bottom.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from oppradar_ai.llm import LLMError
from oppradar_ai.schemas import (
    CertificateExtraction,
    CVExtraction,
    DocumentContent,
    Opportunity,
    OpportunityType,
    PortfolioExtraction,
    Preferences,
    Profile,
)
from pydantic import BaseModel, ValidationError

from app.models import (
    AboutYouStep,
    CertificateIn,
    CVPrefill,
    EducationLevel,
    EducationStep,
    ExperienceIn,
    ExperienceKind,
    GoalsStep,
    LanguageIn,
    LanguageLevel,
    LinkIn,
    LinkKind,
    Me,
    SkillIn,
    SkillsStep,
)

__all__ = ["LLMError", "cv_prefill", "process_document", "to_ai_profile"]


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
# oppradar_ai.documents is imported lazily: it pulls in PyMuPDF (2.x loads an
# ONNX layout model on import) and OCR. Importing it at module level slowed
# every server start and script — and hung them outright when Windows WMI was
# unresponsive (onnxruntime -> platform.system()).
def read(path: Path) -> DocumentContent:
    """File -> text (PDF text layer, OCR for scans). Slow on scans: run off the event loop.

    Raises ValueError for files that cannot be read (corrupt/encrypted PDFs
    surface from PyMuPDF as RuntimeError subclasses).
    """
    from oppradar_ai.documents import read_document

    try:
        return read_document(path)
    except LLMError:
        raise  # vision fallback hit the provider: not the file's fault
    except RuntimeError as exc:
        raise ValueError("the PDF is damaged or protected") from exc


def extract(kind: str, content: DocumentContent) -> BaseModel:
    """Text -> structured extraction for one document kind (one LLM call)."""
    from oppradar_ai.documents import extract_certificate, extract_cv, extract_portfolio

    extractors = {
        "cv": extract_cv,
        "certificate": extract_certificate,
        "portfolio": extract_portfolio,
    }
    return extractors[kind](content.text, content.file_name)


def process_document(path: Path, kind: str) -> tuple[DocumentContent, BaseModel]:
    content = read(path)
    return content, extract(kind, content)


# --------------------------------------------------------------------------- #
# CV extraction -> onboarding prefill ("Here is what we found")
# --------------------------------------------------------------------------- #
_YEAR = re.compile(r"(19|20)\d{2}")

_DEGREE_LEVELS: tuple[tuple[str, EducationLevel], ...] = (
    (r"\b(phd|ph\.d|doctorat|doctorate)\b", "phd"),
    (r"\b(ing[ée]nieur|engineer(ing)?|ingenieur)\b", "engineer"),
    (r"\b(master|msc|m\.sc|mba)\b", "master"),
    (r"\b(licence|bachelor|bsc|b\.sc|ba|lmd)\b", "licence"),
    (r"\b(bac|baccalaur[ée]at)\b", "bac"),
)

_LANGUAGE_LEVELS: tuple[tuple[str, LanguageLevel], ...] = (
    (r"native|mother|fluent|bilingual|c1|c2|courant|maternelle", "fluent"),
    (r"good|intermediate|professional|b1|b2|working|bon", "good"),
    (r"basic|beginner|elementary|notions|a1|a2|d[ée]butant", "basic"),
)

_EXPERIENCE_KINDS: tuple[tuple[str, ExperienceKind], ...] = (
    (r"intern|stage|stagiaire", "internship"),
    (r"hackathon|datathon", "hackathon"),
    (r"volunteer|b[ée]n[ée]vole", "volunteer"),
    (r"competition|contest|olympiad|challenge", "competition"),
)


def _year(value: str | None) -> int | None:
    match = _YEAR.search(value or "")
    return int(match.group(0)) if match else None


def _classify(text: str, table: tuple[tuple[str, Any], ...], default: Any) -> Any:
    for pattern, value in table:
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return default


def _language(raw: str) -> LanguageIn | None:
    name = re.sub(r"\(.*?\)|[-:–].*$", "", raw).strip()
    if not name:
        return None
    level = _classify(raw, _LANGUAGE_LEVELS, "good")
    return LanguageIn(language=name[:40].capitalize(), level=level)


def _link(url: str) -> LinkIn | None:
    kind: LinkKind = (
        "linkedin" if "linkedin.com" in url else "github" if "github.com" in url else "other"
    )
    try:
        return LinkIn(kind=kind, url=url)
    except ValidationError:
        return None


def cv_prefill(extraction: dict[str, Any], today: date | None = None) -> CVPrefill:
    """Map a stored CVExtraction onto the onboarding steps it can pre-fill.

    Only fields the AI extracts today are filled (birth year, nationality,
    wilaya, skill levels are not in CVExtraction yet — the user types them).
    """
    today = today or date.today()
    cv = CVExtraction.model_validate(extraction)

    education = EducationStep()
    if cv.education:
        latest = cv.education[0]  # extractors list the most recent first
        start, end = _year(latest.start_date), _year(latest.end_date)
        education = EducationStep(
            education_level=_classify(latest.degree, _DEGREE_LEVELS, None),
            field_of_study=latest.field[:120] or None,
            institution=latest.institution[:150] or None,
            graduation_year=end,
            current_year=(today.year - start + 1)
            if start and (end is None or end >= today.year) and 0 <= today.year - start < 10
            else None,
        )

    links = [link for url in dict.fromkeys(cv.links) if (link := _link(url))]
    languages = [lang for raw in cv.languages if (lang := _language(raw))]
    seen: set[str] = set()
    skills = []
    for name in cv.skills:
        if name.strip() and name.lower() not in seen and len(skills) < 40:
            seen.add(name.lower())
            skills.append(SkillIn(name=name.strip()[:60]))

    return CVPrefill(
        about=AboutYouStep(
            full_name=cv.full_name[:120] or None,
            country=cv.country[:60] or None,
            languages=languages[:10] or None,
        ),
        education=education,
        skills=SkillsStep(skills=skills or None, interests=cv.interests[:30] or None),
        goals=GoalsStep(links=links[:8] or None),
        experiences=[
            ExperienceIn(
                kind=_classify(f"{e.title} {e.description}", _EXPERIENCE_KINDS, "job"),
                title=(e.title or e.organization or "Experience")[:150],
                organization=e.organization[:150],
                year=_year(e.start_date) or _year(e.end_date),
                description=e.description[:1000],
            )
            for e in cv.experience
            if e.title or e.organization
        ],
        certificates=[
            CertificateIn(
                title=c.title[:150],
                issuer=c.issuer[:150],
                year=_year(c.issued_on),
                credential_url=c.credential_url,
            )
            for c in cv.certificates
            if c.title
        ],
        needs_review=cv.needs_review,
    )


def extraction_model(kind: str) -> type[BaseModel]:
    return {
        "cv": CVExtraction,
        "certificate": CertificateExtraction,
        "portfolio": PortfolioExtraction,
    }[kind]


# --------------------------------------------------------------------------- #
# Web profile -> AI Profile (for matching/chat once those phases land)
# --------------------------------------------------------------------------- #
# The UI offers types the AI enum does not have yet (see docs/ai-interface.md).
_TYPE_FALLBACK = {"datathon": OpportunityType.HACKATHON, "competition": OpportunityType.OTHER}
_HEADLINE_YEAR = {1: "1st", 2: "2nd", 3: "3rd"}


def headline(me: Me) -> str:
    """'3rd-year Computer Science · ENSIA, Algiers' (profile review screen)."""
    year = (
        f"{_HEADLINE_YEAR.get(me.current_year or 0, f'{me.current_year}th')}-year "
        if me.current_year
        else ""
    )
    left = f"{year}{me.field_of_study or ''}".strip()
    right = ", ".join(p for p in (me.institution, me.wilaya) if p)
    return " · ".join(p for p in (left, right) if p)


def to_ai_profile(me: Me) -> Profile:
    types: list[OpportunityType] = []
    for name in me.opportunity_types:
        t = _TYPE_FALLBACK.get(name) or OpportunityType(name)
        if t not in types:
            types.append(t)
    countries = {"algeria": ["Algeria"]}.get(me.preferred_location or "", [])
    modes = ["remote"] if me.preferred_location == "remote" else []
    return Profile(
        user_id=str(me.user_id),
        full_name=me.full_name,
        headline=headline(me),
        email=me.email,
        country=me.country or "",
        skills=[s.name for s in me.skills],
        languages=[f"{lang.language} ({lang.level})" for lang in me.languages],
        interests=me.interests,
        preferences=Preferences(types=types, modes=modes, countries=countries),
        summary=" ".join(p for p in (headline(me), me.goal or "") if p),
        completeness=me.completeness,
    )


def opportunity_row(opp: Opportunity) -> dict[str, Any]:
    """AI Opportunity -> public.opportunities row (upserted on external_id)."""
    data = opp.model_dump(mode="json", exclude={"id"})
    return {**data, "external_id": opp.id or None}


# --------------------------------------------------------------------------- #
# Coming with later AI phases — wire here when they ship:
#   ingestion  -> run_ingestion() -> IngestionReport          (POST /admin/ingest)
#   matching   -> score_matches(profile, opportunities)        (POST /me/agent/start)
#   chat       -> ask(question, history, profile) -> ChatAnswer (POST /chat)
#   notify     -> plan_notifications(matches, settings)        (agent loop)
# --------------------------------------------------------------------------- #
