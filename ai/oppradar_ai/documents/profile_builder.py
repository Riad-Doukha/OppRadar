# Merges per-document extractions (CV/certificate/portfolio) into one Profile:
# union of lists, first-value-wins scalars, conflict + completeness reporting.

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from oppradar_ai.schemas import (
    Certificate,
    CertificateExtraction,
    CVExtraction,
    FieldConfidence,
    PortfolioExtraction,
    Profile,
    ProfileBuildResult,
)

logger = logging.getLogger(__name__)

Extraction = CVExtraction | CertificateExtraction | PortfolioExtraction

# Profile sections used for the completeness score (0..1).
_SECTIONS: tuple[tuple[str, Callable[[Profile], Any]], ...] = (
    ("full_name", lambda p: p.full_name),
    ("e-mail", lambda p: p.email),
    ("headline", lambda p: p.headline),
    ("country", lambda p: p.country),
    ("summary", lambda p: p.summary),
    ("skills", lambda p: p.skills),
    ("languages", lambda p: p.languages),
    ("education", lambda p: p.education),
    ("experience", lambda p: p.experience),
    ("projects or certificates", lambda p: p.projects or p.certificates),
)


def build_profile(
    extractions: list[Extraction],
    user_id: str = "local-user",
    errors: list[str] | None = None,
) -> ProfileBuildResult:
    """Merge document extractions into one Profile with quality reporting.

    Example:
        >>> res = build_profile([cv, certificate])   # doctest: +SKIP
        >>> res.completeness, res.conflicts
        (0.9, [])
    """
    profile = Profile(user_id=user_id)
    conflicts = _merge_scalars(extractions, profile)
    _merge_lists(extractions, profile)
    _merge_items(extractions, profile)
    completeness, suggestions = _score_completeness(profile)
    profile.completeness, profile.completeness_suggestions = completeness, suggestions
    profile.conflicts = conflicts
    profile.source_files = [e.source_file or type(e).__name__ for e in extractions]
    profile.field_confidences = _confidences(extractions, conflicts)
    result = ProfileBuildResult(
        profile=profile,
        merged_from=profile.source_files,
        conflicts=conflicts,
        completeness=completeness,
        suggestions=suggestions,
        document_errors=list(errors or []),
    )
    logger.info(
        "built profile %r from %d docs (completeness=%.2f, %d conflicts)",
        profile.full_name,
        len(extractions),
        completeness,
        len(conflicts),
    )
    return result


def _merge_scalars(extractions: list[Extraction], profile: Profile) -> list[str]:
    """First non-empty value wins; differing values become conflicts."""
    conflicts: list[str] = []
    for field in ("full_name", "email", "headline", "country", "summary"):
        values = [(getattr(e, field, "") or "").strip() for e in extractions]
        present = [v for v in values if v]
        if present:
            setattr(profile, field, present[0])
            distinct = {v.casefold() for v in present}
            if len(distinct) > 1:
                conflicts.append(f"{field}: {' vs '.join(sorted(set(present)))}")
    return conflicts


def _merge_lists(extractions: list[Extraction], profile: Profile) -> None:
    """Union skills/languages/interests, deduplicated case-insensitively."""
    cv = _of(extractions, CVExtraction)
    cert = _of(extractions, CertificateExtraction)
    profile.skills = _union([*(e.skills for e in cv), *(e.skills for e in cert)])
    profile.languages = _union(e.languages for e in cv)
    profile.interests = _union(e.interests for e in cv)


def _merge_items(extractions: list[Extraction], profile: Profile) -> None:
    """Append education/experience/certificates/projects, deduplicated by key."""
    cv_items = [e for e in extractions if isinstance(e, CVExtraction)]
    profile.education = _dedupe([i for e in cv_items for i in e.education], _edu_key)
    profile.experience = _dedupe([i for e in cv_items for i in e.experience], _exp_key)
    certs = [c for e in cv_items for c in e.certificates]
    certs += [_as_certificate(e) for e in extractions if isinstance(e, CertificateExtraction)]
    profile.certificates = _dedupe([c for c in certs if c.title], _cert_key)
    projects = [p for e in cv_items for p in e.projects]
    projects += [p for e in _of(extractions, PortfolioExtraction) for p in e.projects]
    profile.projects = _dedupe([p for p in projects if p.name], _proj_key)


def _score_completeness(profile: Profile) -> tuple[float, list[str]]:
    """Fraction of key sections filled + a suggestion for every empty one."""
    filled = sum(1 for _, getter in _SECTIONS if getter(profile))
    suggestions = [f"Add your {name}" for name, getter in _SECTIONS if not getter(profile)]
    return round(filled / len(_SECTIONS), 2), suggestions


def _confidences(extractions: list[Extraction], conflicts: list[str]) -> list[FieldConfidence]:
    """LLM needs_review fields (0.5) and merge conflicts (0.3) need human eyes."""
    confidences = [
        FieldConfidence(field=field, confidence=0.5, needs_review=True)
        for e in extractions
        for field in e.needs_review
    ]
    confidences += [
        FieldConfidence(field=c.split(":")[0], confidence=0.3, needs_review=True) for c in conflicts
    ]
    return confidences


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _union(groups: Iterable[list[str]]) -> list[str]:
    """Union of string groups, deduplicated case-insensitively (first casing kept)."""
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for item in group:
            key = " ".join(item.casefold().split())
            if key and key not in seen:
                seen.add(key)
                out.append(item)
    return out


def _dedupe(items: list[Any], key: Callable[[Any], tuple]) -> list[Any]:
    seen: set[tuple] = set()
    out = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


def _of(items: list[Extraction], kind: type) -> list:
    return [i for i in items if isinstance(i, kind)]


def _edu_key(e: Any) -> tuple:
    return (" ".join(f"{e.institution} {e.degree} {e.field}".casefold().split()),)


def _exp_key(e: Any) -> tuple:
    return (" ".join(f"{e.organization} {e.title}".casefold().split()),)


def _cert_key(c: Certificate) -> tuple:
    return (" ".join(f"{c.title} {c.issuer}".casefold().split()),)


def _proj_key(p: Any) -> tuple:
    return ((p.url or p.name).casefold(),)


def _as_certificate(ext: CertificateExtraction) -> Certificate:
    return Certificate(
        title=ext.title,
        issuer=ext.issuer,
        issued_on=ext.issued_on,
        hours=ext.hours,
        credential_url=ext.credential_url,
        source_file=ext.source_file,
    )
