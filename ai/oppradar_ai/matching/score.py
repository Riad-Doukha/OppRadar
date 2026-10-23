# The 0-100 score and its parts: semantic similarity (0-1), criteria ratio (0-1)
# and a bonus of trust/language/funding signals (0-1), combined with the weights
# from Settings. Called by: matching/composer.py, notebooks. Every score stays
# reproducible from the parts stored in MatchResult — nothing is hand-tuned.

from __future__ import annotations

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.matching.criteria import normalize_language
from oppradar_ai.schemas import (
    CriteriaStatus,
    EligibilityCriterion,
    Opportunity,
    Profile,
    TrustLevel,
)

# How much each trust level is worth inside the bonus (scams never get this far).
_TRUST_SCORES: dict[TrustLevel, float] = {
    TrustLevel.VERIFIED: 1.0,
    TrustLevel.LIKELY_SAFE: 0.85,
    TrustLevel.UNKNOWN: 0.5,
    TrustLevel.SUSPICIOUS: 0.15,
    TrustLevel.SCAM: 0.0,
}


def criteria_ratio(criteria: list[EligibilityCriterion]) -> float:
    """met / (met + missed); 0.5 when nothing could be checked (neutral).

    UNKNOWN rows are deliberately not counted: a requirement the profile cannot
    show neither helps nor hurts the score.

    Example:
        >>> criteria_ratio([])
        0.5
        >>> criteria_ratio([met, met, missed])
        0.67
    """
    met = sum(1 for c in criteria if c.status is CriteriaStatus.MET)
    missed = sum(1 for c in criteria if c.status is CriteriaStatus.MISSED)
    if not met and not missed:
        return 0.5
    return round(met / (met + missed), 4)


def trust_score(opportunity: Opportunity) -> float:
    """Credibility of the source (1.0 verified ... 0.0 scam)."""
    return _TRUST_SCORES[opportunity.trust_level]


def language_score(profile: Profile, opportunity: Opportunity) -> float:
    """1.0 the offer's language is one the profile speaks, 0.0 mismatch, 0.5 unknown.

    Example:
        >>> language_score(profile_speaking_french, opportunity_in_french)
        1.0
    """
    if not opportunity.language:
        return 0.5
    have = {normalize_language(value) for value in profile.languages if value.strip()}
    if not have:
        return 0.5
    return 1.0 if normalize_language(opportunity.language) in have else 0.0


def funding_score(profile: Profile, opportunity: Opportunity) -> float:
    """1.0 funding is stated, 0.0 when the profile needs it and none is offered.

    Example:
        >>> funding_score(profile_needing_funding, opportunity_without_funding)
        0.0
    """
    if (opportunity.funding or "").strip():
        return 1.0
    return 0.0 if profile.preferences.needs_funding else 0.5


def compute_bonus(
    profile: Profile, opportunity: Opportunity
) -> tuple[float, list[tuple[str, float]]]:
    """Bonus = mean of the three signals, plus the signals themselves (for reasons).

    Example:
        >>> bonus, signals = compute_bonus(profile, opportunity)
        >>> [name for name, _ in signals]
        ['funding', 'language', 'trust']
    """
    signals: list[tuple[str, float]] = [
        ("funding", funding_score(profile, opportunity)),
        ("language", language_score(profile, opportunity)),
        ("trust", trust_score(opportunity)),
    ]
    return round(sum(value for _, value in signals) / len(signals), 3), signals


def combine(
    similarity: float,
    ratio: float,
    bonus: float,
    settings: Settings | None = None,
) -> float:
    """The 0-100 score, using the weights from Settings (so it is reproducible).

    Example:
        >>> combine(1.0, 1.0, 1.0, Settings(llm_provider="fake"))
        100.0
        >>> combine(0.0, 0.5, 0.5, Settings(llm_provider="fake"))
        25.0
    """
    settings = settings or get_settings()
    raw = (
        settings.semantic_weight * similarity
        + settings.criteria_weight * ratio
        + settings.bonus_weight * bonus
    )
    return round(100.0 * raw, 1)
