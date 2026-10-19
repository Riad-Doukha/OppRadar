"""Score opportunities against a profile.

score = 0.45 · embedding similarity
      + 0.40 · skill overlap
      + 0.15 · type-preference bonus

Hard filters run first — see filters.py. All embedding calls are injectable
so tests never touch the network.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import numpy as np

from oppradar_ai.matching import embeddings as emb
from oppradar_ai.matching.filters import hard_filters
from oppradar_ai.matching.reasons import build_reasons
from oppradar_ai.schemas import MatchResult, Opportunity, Profile

WEIGHT_SIMILARITY = 0.45
WEIGHT_SKILL_OVERLAP = 0.40
WEIGHT_TYPE_BONUS = 0.15

EmbedFn = Callable[[list[str]], np.ndarray]


def _type_bonus(profile: Profile, opportunity: Opportunity) -> float:
    """1.0 when the type is explicitly wanted, 0.3 otherwise (neutral)."""
    if not profile.preferences.types:
        return 0.3
    return 1.0 if opportunity.type in profile.preferences.types else 0.0


def score_one(
    profile: Profile,
    opportunity: Opportunity,
    profile_vector: np.ndarray,
    opportunity_vector: np.ndarray,
) -> MatchResult:
    """Score a single (already filtered) opportunity."""
    similarity = float(emb.cosine_similarity_matrix(profile_vector, opportunity_vector)[0])
    similarity = max(0.0, similarity)  # negative cosine = mismatch
    overlap, matched = emb.skill_overlap(profile, opportunity)
    bonus = _type_bonus(profile, opportunity)

    score = (
        WEIGHT_SIMILARITY * similarity
        + WEIGHT_SKILL_OVERLAP * overlap
        + WEIGHT_TYPE_BONUS * bonus
    )
    return MatchResult(
        opportunity=opportunity,
        score=round(min(score, 1.0), 3),
        similarity=round(similarity, 3),
        skill_overlap=overlap,
        type_bonus=bonus,
        reasons=build_reasons(profile, opportunity, similarity=similarity, matched_skills=matched),
    )


def score_matches(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    top_k: int = 20,
    embed_fn: EmbedFn | None = None,
    today: date | None = None,
) -> list[MatchResult]:
    """Filter + score + rank (interface #3 in docs/ai-interface.md).

    `embed_fn` defaults to the configured embedding backend; tests pass a
    deterministic fake to avoid the network.
    """
    survivors = [o for o in opportunities if hard_filters(profile, o, today=today).passed]
    if not survivors:
        return []

    embed_fn = embed_fn or emb.embed_texts
    profile_vector = embed_fn([emb.profile_text(profile)])[0]
    corpus = embed_fn([emb.opportunity_text(o) for o in survivors])

    results = [
        score_one(profile, opportunity, profile_vector, corpus[i])
        for i, opportunity in enumerate(survivors)
    ]
    results.sort(key=lambda m: m.score, reverse=True)
    return results[:top_k]
