# Scoring pipeline: hard filters -> criteria -> embedding similarity -> the 0-100
# score with its reasons (the LLM may only reword reasons, and only for the best
# matches, behind the RUN_LIVE_LLM gate). Called by: api.py (Phase 7), notebooks.

from __future__ import annotations

import logging
from datetime import date

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.embeddings import cosine, get_embedder
from oppradar_ai.llm import get_llm
from oppradar_ai.matching.criteria import check_criteria
from oppradar_ai.matching.filters import apply_hard_filters
from oppradar_ai.matching.reasons import phrase_reasons, phrasing_allowed, rule_reasons
from oppradar_ai.matching.score import combine, compute_bonus, criteria_ratio
from oppradar_ai.matching.texts import opportunity_text, profile_text
from oppradar_ai.schemas import CriteriaStatus, MatchResult, Opportunity, Profile

logger = logging.getLogger(__name__)


def score_user(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    settings: Settings | None = None,
    today: date | None = None,
) -> list[MatchResult]:
    """Every opportunity that survives the hard filters, scored 0-100, best first.

    Example:
        >>> matches = score_user(profile, opportunities)
        >>> [m.score for m in matches] == sorted([m.score for m in matches], reverse=True)
        True
    """
    settings = settings or get_settings()
    outcome = apply_hard_filters(profile, opportunities, today=today)
    similarities = _similarities(profile, outcome.passed, settings)
    matches = [
        _score_one(profile, opportunity, similarity, settings)
        for opportunity, similarity in zip(outcome.passed, similarities, strict=True)
    ]
    matches.sort(key=lambda item: (-item.score, item.opportunity.id))
    rephrased = _phrase_top(matches, settings)
    logger.info(
        "scored %d/%d opportunities for %s (%d dropped, %d rephrased)",
        len(matches),
        len(opportunities),
        profile.user_id,
        len(outcome.dropped),
        rephrased,
    )
    return matches


def _similarities(
    profile: Profile, opportunities: list[Opportunity], settings: Settings
) -> list[float]:
    """Cosine of the one profile vector against every opportunity vector."""
    if not opportunities:
        return []
    embedder = get_embedder(settings)
    profile_vector = embedder.encode_one(profile_text(profile))
    listing_vectors = embedder.encode([opportunity_text(item) for item in opportunities])
    return [cosine(profile_vector, row) for row in listing_vectors]


def _score_one(
    profile: Profile, opportunity: Opportunity, similarity: float, settings: Settings
) -> MatchResult:
    """One MatchResult built from the same rounded values the score is read back from."""
    # A negative cosine (possible with the hashing embedder) means "no overlap":
    # it is stored as 0.0 so the score never goes below its floor.
    similarity = round(min(1.0, max(0.0, float(similarity))), 4)
    criteria = check_criteria(profile, opportunity)
    ratio = criteria_ratio(criteria)
    bonus, signals = compute_bonus(profile, opportunity)
    return MatchResult(
        profile_id=profile.user_id,
        opportunity=opportunity,
        score=combine(similarity, ratio, bonus, settings),
        semantic_similarity=similarity,
        criteria=criteria,
        bonus=bonus,
        top_reasons=rule_reasons(
            profile,
            opportunity,
            similarity=similarity,
            criteria=criteria,
            signals=signals,
            settings=settings,
        ),
        unmet_requirements=[c.text for c in criteria if c.status is CriteriaStatus.MISSED],
    )


def _phrase_top(matches: list[MatchResult], settings: Settings) -> int:
    """Rephrase the best matches' reasons; a closed gate means nothing happens."""
    if not phrasing_allowed(settings):
        return 0
    llm = get_llm()
    targets = [item for item in matches if item.score >= settings.notify_threshold]
    done = 0
    for match in targets[: settings.max_phrases_per_run]:
        original = list(match.top_reasons)
        phrased = phrase_reasons(original, match.opportunity, llm, settings=settings)
        if phrased != original:  # a kept list means the call failed or changed nothing
            match.top_reasons = phrased
            match.reasons_source = "llm"
            done += 1
    logger.info(
        "rephrased %d of %d matches >= %.0f (cap %d)",
        done,
        len(targets),
        settings.notify_threshold,
        settings.max_phrases_per_run,
    )
    return done
